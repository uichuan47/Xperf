import csv
import json
import time
import gc
from typing import Dict, Any, Optional, Iterator
from Processor.TreeNode import TreeNode
from Processor.DefaultProcessors import DefaultNodeProcessor, DefaultFrameProcessor, DefaultTimerNameProcessor
from Processor.BaseProcessors import ITimerNameProcessor, INodeProcessor, IFrameProcessor
from Processor.PerformanceTracker import PerformanceTracker

class CustomTimerNameProcessor(ITimerNameProcessor):
    """自定义TimerName处理器示例"""

    def process_timer_name(self, timer_name: str, timer_id: int, depth: int) -> str:
        """自定义TimerName处理逻辑"""
        processed_name = timer_name

        # 示例：处理特殊的UE函数名格式
        if '::' in processed_name:
            # 提取类名和方法名
            parts = processed_name.split('::')
            if len(parts) >= 2:
                class_name = parts[-2]
                method_name = parts[-1]
                processed_name = f"{class_name}.{method_name}"

        # 示例：简化长路径
        if len(processed_name) > 50:
            processed_name = processed_name[:47] + "..."

        return processed_name

    def extract_metadata(self, timer_name: str, timer_id: int) -> Dict[str, Any]:
        """提取自定义元数据"""
        metadata = {}

        # 提取命名空间信息
        if '::' in timer_name:
            parts = timer_name.split('::')
            metadata['namespace'] = parts[0] if len(parts) > 1 else ''
            metadata['class_name'] = parts[-2] if len(parts) > 1 else ''
            metadata['method_name'] = parts[-1] if len(parts) > 0 else ''

        # 检查是否是蓝图相关
        metadata['is_blueprint'] = 'Blueprint' in timer_name or 'BP_' in timer_name

        # 检查是否是C++相关
        metadata['is_cpp'] = '::' in timer_name and not metadata['is_blueprint']

        return metadata




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

    # 处理节点
    processed_root = node_processor.process_node(root)

    # 递归处理子节点
    filtered_children = []
    for child in root.children:
        filtered_child = filter_tree_nodes(child, node_processor)
        if filtered_child:
            filtered_children.append(filtered_child)

    processed_root.children = filtered_children
    return processed_root


def parse_csv_to_trees_generator(csv_file_path: str, tracker: PerformanceTracker,
                                 timer_processor: ITimerNameProcessor = None,
                                 node_processor: INodeProcessor = None,
                                 frame_processor: IFrameProcessor = None) -> Iterator[Dict[str, Any]]:
    """
    生成器函数，逐帧解析CSV文件

    Args:
        csv_file_path: CSV文件路径
        tracker: 性能跟踪器
        timer_processor: TimerName处理器
        node_processor: 节点处理器
        frame_processor: 帧处理器

    Yields:
        每一帧的树结构字典
    """
    # 使用默认处理器
    if timer_processor is None:
        timer_processor = DefaultTimerNameProcessor()
    if node_processor is None:
        node_processor = DefaultNodeProcessor()
    if frame_processor is None:
        frame_processor = DefaultFrameProcessor()

    current_frame_root = None
    node_stack = []
    frame_index = 0

    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            parse_start = time.time()

            # 解析行数据
            timer_id = int(row['TimerId'])
            timer_name = row['TimerName']
            start_time = float(row['StartTime'])
            end_time = float(row['EndTime'])
            duration = float(row['Duration'])
            depth = int(row['Depth'])

            # 处理TimerName
            processed_timer_name = timer_processor.process_timer_name(timer_name, timer_id, depth)

            # 创建新节点
            node = TreeNode(timer_id, processed_timer_name, start_time, end_time, duration, depth)

            # 提取元数据
            node.metadata = timer_processor.extract_metadata(timer_name, timer_id)

            # 如果是根节点（depth=0），说明是新的一帧
            if depth == 0:
                # 如果之前有完整的帧，处理并返回它
                if current_frame_root is not None:
                    frame_index += 1

                    # 检查是否应该包含此帧
                    should_include = frame_processor.should_include_frame(current_frame_root, frame_index)

                    if should_include:
                        # 处理帧
                        processed_frame = frame_processor.process_frame(current_frame_root, frame_index)

                        # 过滤节点
                        convert_start = time.time()
                        filtered_frame = filter_tree_nodes(processed_frame, node_processor)
                        convert_time = time.time() - convert_start

                        if filtered_frame:
                            original_count = count_nodes_in_tree(current_frame_root)
                            filtered_count = count_nodes_in_tree(filtered_frame)

                            parse_time = parse_start - (convert_start - convert_time)
                            tracker.track_frame(original_count, filtered_count, parse_time, convert_time, True)

                            # 清理引用
                            current_frame_root = None
                            node_stack.clear()
                            yield filtered_frame.to_dict()
                        else:
                            # 整帧被过滤
                            original_count = count_nodes_in_tree(current_frame_root)
                            parse_time = parse_start - (convert_start - convert_time)
                            tracker.track_frame(original_count, 0, parse_time, convert_time, False)
                    else:
                        # 帧被过滤
                        original_count = count_nodes_in_tree(current_frame_root)
                        tracker.track_frame(original_count, 0, 0.001, 0.001, False)

                    # 清理引用
                    current_frame_root = None
                    node_stack.clear()

                # 开始新的一帧
                current_frame_root = node
                node_stack = [node]
            else:
                # 非根节点
                while len(node_stack) > depth:
                    node_stack.pop()

                if node_stack:
                    parent = node_stack[-1]
                    parent.children.append(node)

                node_stack.append(node)

        # 处理最后一帧
        if current_frame_root is not None:
            frame_index += 1
            should_include = frame_processor.should_include_frame(current_frame_root, frame_index)

            if should_include:
                processed_frame = frame_processor.process_frame(current_frame_root, frame_index)
                filtered_frame = filter_tree_nodes(processed_frame, node_processor)

                if filtered_frame:
                    original_count = count_nodes_in_tree(current_frame_root)
                    filtered_count = count_nodes_in_tree(filtered_frame)
                    tracker.track_frame(original_count, filtered_count, 0.001, 0.001, True)
                    yield filtered_frame.to_dict()


def process_csv_with_processors(csv_file_path: str, output_file_path: str = None,
                                write_json: bool = True, batch_size: int = 100,
                                timer_processor: ITimerNameProcessor = None,
                                node_processor: INodeProcessor = None,
                                frame_processor: IFrameProcessor = None) -> Dict[str, Any]:
    """
    使用自定义处理器处理CSV文件

    Args:
        csv_file_path: 输入CSV文件路径
        output_file_path: 输出JSON文件路径
        write_json: 是否写入JSON文件
        batch_size: 批处理大小
        timer_processor: TimerName处理器
        node_processor: 节点处理器
        frame_processor: 帧处理器

    Returns:
        处理统计信息
    """
    tracker = PerformanceTracker()
    tracker.start_tracking()

    output_file = None
    first_frame = True
    batch = []

    try:
        if write_json and output_file_path:
            output_file = open(output_file_path, 'w', encoding='utf-8')
            output_file.write('[')
            print(f"JSON输出文件: {output_file_path}")
        else:
            print("仅解析模式 - 不写入JSON文件")

        print("-" * 90)
        print("帧序号   | 节点数(原→过滤) | 解析时间 | 转换时间 | 总计时间 | 累计时间 | 状态")
        print("-" * 90)

        for frame_tree in parse_csv_to_trees_generator(csv_file_path, tracker,
                                                       timer_processor, node_processor, frame_processor):
            if write_json and output_file:
                batch.append(frame_tree)

                if len(batch) >= batch_size:
                    for frame in batch:
                        if not first_frame:
                            output_file.write(',')
                        json.dump(frame, output_file, separators=(',', ':'))
                        first_frame = False

                    batch.clear()
                    gc.collect()

            # 进度摘要
            if tracker.frame_count % 500 == 0:
                summary = tracker.get_summary()
                print("-" * 90)
                print(f"进度摘要 - 已处理 {tracker.frame_count:,} 帧:")
                print(f"  包含帧: {summary['included_frames']:,} | 过滤帧: {summary['filtered_frames']:,}")
                print(f"  包含节点: {summary['included_nodes']:,} | 过滤节点: {summary['filtered_nodes']:,}")
                print(f"  处理速度: {summary['frames_per_second']:.1f} 帧/秒")
                print("-" * 90)

        # 处理剩余批次
        if write_json and output_file and batch:
            for frame in batch:
                if not first_frame:
                    output_file.write(',')
                json.dump(frame, output_file, separators=(',', ':'))
                first_frame = False

        if write_json and output_file:
            output_file.write(']')

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

            if total_rows % 10000 == 0:
                print(f"  已读取 {total_rows:,} 行...")

    analysis_time = time.time() - start_time

    return {
        'total_rows': total_rows,
        'frame_count': frame_count,
        'max_depth': max_depth,
        'unique_timer_names': len(timer_names),
        'avg_nodes_per_frame': total_rows / frame_count if frame_count > 0 else 0,
        'analysis_time': analysis_time,
        'timer_names_sample': list(timer_names)[:20]  # 前20个TimerName作为样本
    }


def print_final_summary(stats: Dict[str, Any], summary: Dict[str, Any]):
    """打印最终统计摘要"""
    print("\n" + "=" * 80)
    print("处理完成！最终统计报告:")
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
    print(f"  帧过滤率: {summary['filtered_frames'] / summary['total_frames'] * 100:.1f}%")
    print(f"  节点过滤率: {summary['filtered_nodes'] / summary['total_nodes'] * 100:.1f}%")

    print(f"\n性能统计:")
    print(f"  总处理时间: {summary['total_time']:.2f} 秒")
    print(f"  平均每帧时间: {summary['avg_time_per_frame'] * 1000:.2f} 毫秒")
    print(f"  处理速度: {summary['frames_per_second']:.1f} 帧/秒")

    # 显示TimerName样本
    print(f"\nTimerName样本:")
    for i, name in enumerate(stats['timer_names_sample'][:10]):
        print(f"  {i + 1:2d}. {name}")


def main():
    """主函数"""
    csv_file_path = r"UE55Timer.csv"
    json_file_path = "frame_trees.json"

    # 处理选项
    write_json = True
    batch_size = 50

    # 创建自定义处理器
    timer_processor = DefaultTimerNameProcessor()  # 或者使用 DefaultTimerNameProcessor()

    node_processor = DefaultNodeProcessor(
        min_duration=0,  # 过滤掉小于0.1ms的节点
        exclude_categories=['']  # 排除内存相关的节点
    )

    frame_processor = DefaultFrameProcessor(
        min_frame_duration=0,  # 过滤掉小于1ms的帧
        max_frame_count=None  # 不限制帧数
    )

    try:
        print("UTrace CSV 解析器 (带自定义处理器)")
        print("=" * 60)

        # 分析文件
        stats = get_csv_stats(csv_file_path)
        print(f"\n文件分析完成 (用时 {stats['analysis_time']:.2f}s):")
        print(f"  总行数: {stats['total_rows']:,}")
        print(f"  帧数: {stats['frame_count']:,}")
        print(f"  唯一TimerName: {stats['unique_timer_names']:,}")
        print(f"  最大深度: {stats['max_depth']}")

        print(f"\n开始处理...")
        print(f"写入JSON: {'是' if write_json else '否'}")
        print(f"使用自定义TimerName处理器: {type(timer_processor).__name__}")
        print(f"使用节点过滤器: 最小持续时间={node_processor.min_duration * 1000:.1f}ms")

        # 处理文件
        summary = process_csv_with_processors(
            csv_file_path=csv_file_path,
            output_file_path=json_file_path if write_json else None,
            write_json=write_json,
            batch_size=batch_size,
            timer_processor=timer_processor,
            node_processor=node_processor,
            frame_processor=frame_processor
        )

        # 打印最终摘要
        print_final_summary(stats, summary)

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
