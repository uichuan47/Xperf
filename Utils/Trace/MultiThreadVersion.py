import csv
import json
import time
import gc
import re
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Iterator, Callable, Tuple
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import multiprocessing as mp


# 保持之前的类定义不变
class TreeNode:
    def __init__(self, timer_id: int, timer_name: str, start_time: float,
                 end_time: float, duration: float, depth: int):
        self.timer_id = timer_id
        self.timer_name = timer_name
        self.start_time = start_time
        self.end_time = end_time
        self.duration = duration
        self.depth = depth
        self.children: List[TreeNode] = []
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        """将树节点转换为字典格式"""
        result = {
            "timer_id": self.timer_id,
            "timer_name": self.timer_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "depth": self.depth,
            "children": [child.to_dict() for child in self.children]
        }

        if self.metadata:
            result["metadata"] = self.metadata

        return result


# 保持接口定义不变
class ITimerNameProcessor(ABC):
    @abstractmethod
    def process_timer_name(self, timer_name: str, timer_id: int, depth: int) -> str:
        pass

    @abstractmethod
    def extract_metadata(self, timer_name: str, timer_id: int) -> Dict[str, Any]:
        pass


class INodeProcessor(ABC):
    @abstractmethod
    def should_include_node(self, node: TreeNode) -> bool:
        pass

    @abstractmethod
    def process_node(self, node: TreeNode) -> TreeNode:
        pass


class IFrameProcessor(ABC):
    @abstractmethod
    def should_include_frame(self, frame_root: TreeNode, frame_index: int) -> bool:
        pass

    @abstractmethod
    def process_frame(self, frame_root: TreeNode, frame_index: int) -> TreeNode:
        pass


# 默认处理器实现
class DefaultTimerNameProcessor(ITimerNameProcessor):
    def __init__(self):
        self.cleanup_patterns = [
            (r'^STAT_', ''),
            (r'_+', '_'),
            (r'^_|_$', ''),
        ]

        self.category_patterns = {
            'Engine': [r'.*Engine.*', r'.*Loop.*'],
            'Rendering': [r'.*Render.*', r'.*Draw.*', r'.*GPU.*'],
            'Physics': [r'.*Physics.*', r'.*Collision.*'],
            'Audio': [r'.*Audio.*', r'.*Sound.*'],
            'Animation': [r'.*Anim.*', r'.*Bone.*'],
            'AI': [r'.*AI.*', r'.*Behavior.*'],
            'Network': [r'.*Net.*', r'.*Network.*'],
            'Memory': [r'.*Malloc.*', r'.*Memory.*', r'.*GC.*'],
            'IO': [r'.*File.*', r'.*Load.*', r'.*Save.*'],
        }

    def process_timer_name(self, timer_name: str, timer_id: int, depth: int) -> str:
        processed_name = timer_name
        for pattern, replacement in self.cleanup_patterns:
            processed_name = re.sub(pattern, replacement, processed_name)
        return processed_name

    def extract_metadata(self, timer_name: str, timer_id: int) -> Dict[str, Any]:
        metadata = {}
        category = 'Other'
        for cat, patterns in self.category_patterns.items():
            if any(re.match(pattern, timer_name, re.IGNORECASE) for pattern in patterns):
                category = cat
                break

        metadata['category'] = category
        numbers = re.findall(r'\d+', timer_name)
        if numbers:
            metadata['numbers'] = [int(n) for n in numbers]
        metadata['is_stat'] = timer_name.startswith('STAT_')

        return metadata


class DefaultNodeProcessor(INodeProcessor):
    def __init__(self, min_duration: float = 0.0, exclude_categories: List[str] = None):
        self.min_duration = min_duration
        self.exclude_categories = exclude_categories or []

    def should_include_node(self, node: TreeNode) -> bool:
        if node.duration < self.min_duration:
            return False
        if 'category' in node.metadata:
            if node.metadata['category'] in self.exclude_categories:
                return False
        return True

    def process_node(self, node: TreeNode) -> TreeNode:
        if node.duration > 0.01:
            node.metadata['performance_level'] = 'slow'
        elif node.duration > 0.001:
            node.metadata['performance_level'] = 'normal'
        else:
            node.metadata['performance_level'] = 'fast'
        return node


class DefaultFrameProcessor(IFrameProcessor):
    def __init__(self, min_frame_duration: float = 0.0, max_frame_count: int = None):
        self.min_frame_duration = min_frame_duration
        self.max_frame_count = max_frame_count

    def should_include_frame(self, frame_root: TreeNode, frame_index: int) -> bool:
        if self.max_frame_count and frame_index > self.max_frame_count:
            return False
        if frame_root.duration < self.min_frame_duration:
            return False
        return True

    def process_frame(self, frame_root: TreeNode, frame_index: int) -> TreeNode:
        frame_root.metadata['frame_index'] = frame_index
        frame_root.metadata['fps'] = 1.0 / frame_root.duration if frame_root.duration > 0 else 0

        if frame_root.duration > 0.033:
            frame_root.metadata['frame_performance'] = 'poor'
        elif frame_root.duration > 0.016:
            frame_root.metadata['frame_performance'] = 'acceptable'
        else:
            frame_root.metadata['frame_performance'] = 'good'

        return frame_root


# 多线程相关的数据结构
class FrameData:
    """帧数据容器"""

    def __init__(self, frame_index: int, rows: List[Dict[str, str]]):
        self.frame_index = frame_index
        self.rows = rows
        self.node_count = len(rows)


class ProcessedFrame:
    """处理后的帧数据"""

    def __init__(self, frame_index: int, frame_dict: Dict[str, Any],
                 original_nodes: int, filtered_nodes: int,
                 parse_time: float, convert_time: float, included: bool):
        self.frame_index = frame_index
        self.frame_dict = frame_dict
        self.original_nodes = original_nodes
        self.filtered_nodes = filtered_nodes
        self.parse_time = parse_time
        self.convert_time = convert_time
        self.included = included


class ThreadSafePerformanceTracker:
    """线程安全的性能跟踪器"""

    def __init__(self):
        self.start_time = None
        self.frame_count = 0
        self.total_nodes = 0
        self.filtered_nodes = 0
        self.filtered_frames = 0
        self.parsing_times = []
        self.conversion_times = []
        self._lock = threading.Lock()

    def start_tracking(self):
        with self._lock:
            self.start_time = time.time()
            print(f"开始多线程解析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def track_frame(self, processed_frame: ProcessedFrame):
        with self._lock:
            self.frame_count += 1
            self.total_nodes += processed_frame.original_nodes
            self.filtered_nodes += processed_frame.filtered_nodes

            if not processed_frame.included:
                self.filtered_frames += 1

            self.parsing_times.append(processed_frame.parse_time)
            self.conversion_times.append(processed_frame.convert_time)

            # 输出进度信息
            if self.frame_count % 50 == 0:  # 减少输出频率
                elapsed = time.time() - self.start_time
                fps = self.frame_count / elapsed if elapsed > 0 else 0
                status = "INCLUDED" if processed_frame.included else "FILTERED"

                print(f"帧 {processed_frame.frame_index:6d} | "
                      f"节点: {processed_frame.original_nodes:4d}→{processed_frame.filtered_nodes:4d} | "
                      f"解析: {processed_frame.parse_time * 1000:6.2f}ms | "
                      f"转换: {processed_frame.convert_time * 1000:6.2f}ms | "
                      f"累计: {elapsed:7.2f}s | "
                      f"速度: {fps:6.1f}帧/s | "
                      f"状态: {status}")

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            total_time = time.time() - self.start_time if self.start_time else 0

            return {
                'total_frames': self.frame_count,
                'filtered_frames': self.filtered_frames,
                'included_frames': self.frame_count - self.filtered_frames,
                'total_nodes': self.total_nodes,
                'filtered_nodes': self.filtered_nodes,
                'included_nodes': self.total_nodes - self.filtered_nodes,
                'total_time': total_time,
                'avg_nodes_per_frame': self.total_nodes / self.frame_count if self.frame_count > 0 else 0,
                'avg_time_per_frame': total_time / self.frame_count if self.frame_count > 0 else 0,
                'avg_parsing_time': sum(self.parsing_times) / len(self.parsing_times) if self.parsing_times else 0,
                'avg_conversion_time': sum(self.conversion_times) / len(
                    self.conversion_times) if self.conversion_times else 0,
                'frames_per_second': self.frame_count / total_time if total_time > 0 else 0
            }


# CSV读取和帧分割
def read_csv_and_split_frames(csv_file_path: str, max_frames: int = None) -> Iterator[FrameData]:
    """
    读取CSV文件并按帧分割数据
    """
    current_frame_rows = []
    frame_index = 0

    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            depth = int(row['Depth'])

            if depth == 0:
                if current_frame_rows:
                    yield FrameData(frame_index, current_frame_rows.copy())
                    frame_index += 1

                    if max_frames and frame_index >= max_frames:
                        break

                    current_frame_rows.clear()

                current_frame_rows.append(row)
            else:
                current_frame_rows.append(row)

        if current_frame_rows:
            yield FrameData(frame_index, current_frame_rows)


# 单帧处理函数
def count_nodes_in_tree(root: TreeNode) -> int:
    """计算树中节点总数"""
    count = 1
    for child in root.children:
        count += count_nodes_in_tree(child)
    return count


def filter_tree_nodes(root: TreeNode, node_processor: INodeProcessor) -> Optional[TreeNode]:
    """递归过滤树节点"""
    if not node_processor.should_include_node(root):
        return None

    processed_root = node_processor.process_node(root)

    filtered_children = []
    for child in root.children:
        filtered_child = filter_tree_nodes(child, node_processor)
        if filtered_child:
            filtered_children.append(filtered_child)

    processed_root.children = filtered_children
    return processed_root


def process_single_frame(frame_data: FrameData,
                         timer_processor: ITimerNameProcessor,
                         node_processor: INodeProcessor,
                         frame_processor: IFrameProcessor) -> ProcessedFrame:
    """
    处理单个帧的数据
    """
    parse_start = time.time()

    try:
        # 构建树结构
        frame_root = None
        node_stack = []

        for row in frame_data.rows:
            timer_id = int(row['TimerId'])
            timer_name = row['TimerName']
            start_time = float(row['StartTime'])
            end_time = float(row['EndTime'])
            duration = float(row['Duration'])
            depth = int(row['Depth'])

            # 处理TimerName
            processed_timer_name = timer_processor.process_timer_name(timer_name, timer_id, depth)

            # 创建节点
            node = TreeNode(timer_id, processed_timer_name, start_time, end_time, duration, depth)
            node.metadata = timer_processor.extract_metadata(timer_name, timer_id)

            if depth == 0:
                frame_root = node
                node_stack = [node]
            else:
                # 调整栈深度
                while len(node_stack) > depth:
                    node_stack.pop()

                if node_stack:
                    parent = node_stack[-1]
                    parent.children.append(node)

                node_stack.append(node)

        parse_time = time.time() - parse_start

        if frame_root is None:
            return ProcessedFrame(frame_data.frame_index, {}, 0, 0, parse_time, 0, False)

        # 检查是否应该包含此帧
        should_include = frame_processor.should_include_frame(frame_root, frame_data.frame_index)

        if not should_include:
            original_count = count_nodes_in_tree(frame_root)
            return ProcessedFrame(frame_data.frame_index, {}, original_count, 0, parse_time, 0, False)

        # 处理帧
        convert_start = time.time()
        processed_frame = frame_processor.process_frame(frame_root, frame_data.frame_index)

        # 过滤节点
        filtered_frame = filter_tree_nodes(processed_frame, node_processor)

        if filtered_frame is None:
            original_count = count_nodes_in_tree(frame_root)
            convert_time = time.time() - convert_start
            return ProcessedFrame(frame_data.frame_index, {}, original_count, 0, parse_time, convert_time, False)

        # 转换为字典
        frame_dict = filtered_frame.to_dict()
        convert_time = time.time() - convert_start

        original_count = count_nodes_in_tree(frame_root)
        filtered_count = count_nodes_in_tree(filtered_frame)

        return ProcessedFrame(frame_data.frame_index, frame_dict, original_count,
                              filtered_count, parse_time, convert_time, True)

    except Exception as e:
        print(f"处理帧 {frame_data.frame_index} 时出错: {e}")
        parse_time = time.time() - parse_start
        return ProcessedFrame(frame_data.frame_index, {}, 0, 0, parse_time, 0, False)


# 修复后的多线程处理主函数
def process_csv_multithreaded(csv_file_path: str, output_file_path: str = None,
                              write_json: bool = True,
                              num_workers: int = None,
                              batch_size: int = 100,
                              max_frames: int = None,
                              timer_processor: ITimerNameProcessor = None,
                              node_processor: INodeProcessor = None,
                              frame_processor: IFrameProcessor = None) -> Dict[str, Any]:
    """
    多线程处理CSV文件 - 修复版本
    """
    if num_workers is None:
        num_workers = min(mp.cpu_count(), 8)

    # 使用默认处理器
    if timer_processor is None:
        timer_processor = DefaultTimerNameProcessor()
    if node_processor is None:
        node_processor = DefaultNodeProcessor()
    if frame_processor is None:
        frame_processor = DefaultFrameProcessor()

    tracker = ThreadSafePerformanceTracker()
    tracker.start_tracking()

    print(f"使用 {num_workers} 个工作线程")
    print(f"批处理大小: {batch_size}")
    if max_frames:
        print(f"最大处理帧数: {max_frames:,}")

    output_file = None
    first_frame = True

    try:
        if write_json and output_file_path:
            output_file = open(output_file_path, 'w', encoding='utf-8')
            output_file.write('[')
            print(f"JSON输出文件: {output_file_path}")
        else:
            print("仅解析模式 - 不写入JSON文件")

        print("-" * 90)
        print("多线程处理进度:")
        print("-" * 90)

        # 改进的多线程处理逻辑
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # 收集所有帧数据
            frame_data_list = list(read_csv_and_split_frames(csv_file_path, max_frames))
            total_frames = len(frame_data_list)
            print(f"总共需要处理 {total_frames} 帧")

            if total_frames == 0:
                print("没有找到有效的帧数据")
                return tracker.get_summary()

            # 分批处理，避免内存问题
            processed_count = 0
            frame_buffer = {}  # 用于保持帧的顺序
            next_frame_to_write = 0

            # 按批次处理帧
            for batch_start in range(0, total_frames, batch_size):
                batch_end = min(batch_start + batch_size, total_frames)
                batch_frames = frame_data_list[batch_start:batch_end]

                print(f"处理批次 {batch_start // batch_size + 1}/{(total_frames - 1) // batch_size + 1}: "
                      f"帧 {batch_start} - {batch_end - 1}")

                # 提交当前批次的任务
                future_to_frame = {}
                for frame_data in batch_frames:
                    future = executor.submit(process_single_frame, frame_data,
                                             timer_processor, node_processor, frame_processor)
                    future_to_frame[future] = frame_data.frame_index

                # 等待当前批次完成
                for future in as_completed(future_to_frame.keys()):  # 移除timeout参数
                    try:
                        processed_frame = future.result()
                        frame_index = future_to_frame[future]

                        # 跟踪性能
                        tracker.track_frame(processed_frame)

                        # 缓存结果以保持顺序
                        if processed_frame.included:
                            frame_buffer[frame_index] = processed_frame.frame_dict

                        processed_count += 1

                    except Exception as e:
                        print(f"处理帧时出错: {e}")
                        processed_count += 1

                # 按顺序写入已完成的帧
                if write_json and output_file:
                    while next_frame_to_write in frame_buffer:
                        if not first_frame:
                            output_file.write(',\n')  # 添加换行符便于调试
                        json.dump(frame_buffer[next_frame_to_write], output_file, separators=(',', ':'))
                        first_frame = False
                        del frame_buffer[next_frame_to_write]
                        next_frame_to_write += 1

                # 强制垃圾回收
                gc.collect()

                # 输出批次完成信息
                progress = processed_count / total_frames * 100
                print(f"批次完成，总进度: {progress:.1f}% ({processed_count}/{total_frames})")

            # 写入剩余的帧（处理可能的乱序情况）
            if write_json and output_file:
                remaining_frames = sorted([idx for idx in frame_buffer.keys() if idx >= next_frame_to_write])
                for frame_idx in remaining_frames:
                    if not first_frame:
                        output_file.write(',\n')
                    json.dump(frame_buffer[frame_idx], output_file, separators=(',', ':'))
                    first_frame = False

        if write_json and output_file:
            output_file.write('\n]')  # 添加换行符

        print(f"\n处理完成！总共处理了 {processed_count} 帧")

    except Exception as e:
        print(f"多线程处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if output_file:
            output_file.close()

    return tracker.get_summary()


def get_csv_stats(csv_file_path: str) -> Dict[str, Any]:
    """快速统计CSV文件信息"""
    print("正在分析CSV文件结构...")
    start_time = time.time()

    total_rows = 0
    frame_count = 0
    max_depth = 0
    timer_names = set()

    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)

            for row in reader:
                total_rows += 1
                depth = int(row['Depth'])
                timer_name = row['TimerName']

                if depth == 0:
                    frame_count += 1

                max_depth = max(max_depth, depth)
                timer_names.add(timer_name)

                if total_rows % 20000 == 0:
                    print(f"  已读取 {total_rows:,} 行...")

    except Exception as e:
        print(f"分析CSV文件时出错: {e}")
        return {
            'total_rows': 0,
            'frame_count': 0,
            'max_depth': 0,
            'unique_timer_names': 0,
            'avg_nodes_per_frame': 0,
            'analysis_time': 0,
            'timer_names_sample': []
        }

    analysis_time = time.time() - start_time

    return {
        'total_rows': total_rows,
        'frame_count': frame_count,
        'max_depth': max_depth,
        'unique_timer_names': len(timer_names),
        'avg_nodes_per_frame': total_rows / frame_count if frame_count > 0 else 0,
        'analysis_time': analysis_time,
        'timer_names_sample': list(timer_names)[:20]
    }


def print_final_summary(stats: Dict[str, Any], summary: Dict[str, Any]):
    """打印最终统计摘要"""
    print("\n" + "=" * 80)
    print("多线程处理完成！最终统计报告:")
    print("=" * 80)

    print(f"文件信息:")
    print(f"  总行数: {stats['total_rows']:,}")
    print(f"  总帧数: {summary['total_frames']:,}")
    print(f"  唯一TimerName数: {stats['unique_timer_names']:,}")
    print(f"  最大深度: {stats['max_depth']}")

    print(f"\n过滤统计:")
    print(f"  包含帧数: {summary['included_frames']:,}")
    print(f"  过滤帧数: {summary['filtered_frames']:,}")
    print(f"  包含节点数: {summary['included_nodes']:,}")
    print(f"  过滤节点数: {summary['filtered_nodes']:,}")
    if summary['total_frames'] > 0:
        print(f"  帧过滤率: {summary['filtered_frames'] / summary['total_frames'] * 100:.1f}%")
    if summary['total_nodes'] > 0:
        print(f"  节点过滤率: {summary['filtered_nodes'] / summary['total_nodes'] * 100:.1f}%")

    print(f"\n性能统计:")
    print(f"  总处理时间: {summary['total_time']:.2f} 秒")
    if summary['total_frames'] > 0:
        print(f"  平均每帧时间: {summary['avg_time_per_frame'] * 1000:.2f} 毫秒")
    print(f"  处理速度: {summary['frames_per_second']:.1f} 帧/秒")
    if summary['total_time'] > 0 and summary['included_nodes'] > 0:
        print(f"  节点处理速度: {summary['included_nodes'] / summary['total_time']:.0f} 节点/秒")

    # 多线程效率估算
    if summary['frames_per_second'] > 0:
        theoretical_max_fps = summary['frames_per_second'] * mp.cpu_count()
        print(f"  理论最大速度: {theoretical_max_fps:.1f} 帧/秒")
        efficiency = min(100.0, summary['frames_per_second'] / theoretical_max_fps * 100)
        print(f"  多线程效率: {efficiency:.1f}%")


def main():
    """主函数"""
    csv_file_path = "UE55Timer.csv"
    json_file_path = "frame_trees_mt.json"

    # 处理选项
    write_json = False
    use_multithreading = True
    num_workers = None  # 自动检测
    batch_size = 50  # 减小批处理大小，降低内存使用
    max_frames = None  # 处理所有帧

    # 创建处理器
    timer_processor = DefaultTimerNameProcessor()
    node_processor = DefaultNodeProcessor(
        min_duration=0.0001,
        exclude_categories=[]
    )
    frame_processor = DefaultFrameProcessor(
        min_frame_duration=0.001,
        max_frame_count=max_frames
    )

    try:
        print("UTrace CSV 多线程解析器 (修复版)")
        print("=" * 60)

        # 分析文件
        stats = get_csv_stats(csv_file_path)

        if stats['frame_count'] == 0:
            print("错误：没有找到有效的帧数据")
            return

        print(f"\n文件分析完成 (用时 {stats['analysis_time']:.2f}s):")
        print(f"  总行数: {stats['total_rows']:,}")
        print(f"  帧数: {stats['frame_count']:,}")
        print(f"  唯一TimerName: {stats['unique_timer_names']:,}")
        print(f"  最大深度: {stats['max_depth']}")
        print(f"  平均每帧节点数: {stats['avg_nodes_per_frame']:.1f}")

        # 根据文件大小决定是否使用多线程
        if stats['frame_count'] < 50:
            use_multithreading = False
            print(f"\n帧数较少，建议使用单线程处理")

        print(f"\n处理配置:")
        print(f"  多线程: {'是' if use_multithreading else '否'}")
        if use_multithreading:
            actual_workers = num_workers or min(mp.cpu_count(), 8)
            print(f"  工作线程数: {actual_workers}")
        print(f"  写入JSON: {'是' if write_json else '否'}")
        print(f"  批处理大小: {batch_size}")
        print(f"  最小节点持续时间: {node_processor.min_duration * 1000:.1f}ms")

        # 处理文件
        if use_multithreading:
            summary = process_csv_multithreaded(
                csv_file_path=csv_file_path,
                output_file_path=json_file_path if write_json else None,
                write_json=write_json,
                num_workers=num_workers,
                batch_size=batch_size,
                max_frames=max_frames,
                timer_processor=timer_processor,
                node_processor=node_processor,
                frame_processor=frame_processor
            )
        else:
            print("单线程处理功能需要单独实现")
            return

        # 打印最终摘要
        print_final_summary(stats, summary)

        # 性能建议
        if summary['frames_per_second'] < 50:
            print(f"\n性能建议:")
            print(f"  - 当前处理速度较慢，可以考虑:")
            print(f"    * 增加最小持续时间过滤 (当前: {node_processor.min_duration * 1000:.1f}ms)")
            print(f"    * 排除更多不需要的节点类别")
            print(f"    * 减小批处理大小以降低内存使用")
            print(f"    * 使用SSD存储设备")

    except FileNotFoundError:
        print(f"错误：找不到文件 {csv_file_path}")
    except KeyboardInterrupt:
        print(f"\n用户中断处理过程")
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()