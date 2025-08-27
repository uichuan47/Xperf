from datetime import datetime
from typing import List, Dict, Any, Optional, Iterator, Callable
import time

class PerformanceTracker:
    """性能跟踪器"""

    def __init__(self):
        self.start_time = None
        self.last_frame_time = None
        self.frame_count = 0
        self.total_nodes = 0
        self.filtered_nodes = 0
        self.filtered_frames = 0
        self.parsing_times = []
        self.conversion_times = []

    def start_tracking(self):
        """开始跟踪"""
        self.start_time = time.time()
        self.last_frame_time = self.start_time
        print(f"开始解析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def track_frame(self, node_count: int, filtered_count: int, parse_time: float,
                    convert_time: float, included: bool = True):
        """记录单帧处理信息"""
        current_time = time.time()
        self.frame_count += 1
        self.total_nodes += node_count
        self.filtered_nodes += filtered_count

        if not included:
            self.filtered_frames += 1

        self.parsing_times.append(parse_time)
        self.conversion_times.append(convert_time)

        # 计算速度信息
        elapsed_total = current_time - self.start_time
        elapsed_since_last = current_time - self.last_frame_time
        avg_time_per_frame = elapsed_total / self.frame_count

        # 输出详细信息
        status = "INCLUDED" if included else "FILTERED"
        print(f"帧 {self.frame_count:6d} | "
              f"节点: {node_count:4d}→{filtered_count:4d} | "
              f"解析: {parse_time * 1000:6.2f}ms | "
              f"转换: {convert_time * 1000:6.2f}ms | "
              f"总计: {(parse_time + convert_time) * 1000:6.2f}ms | "
              f"累计: {elapsed_total:7.2f}s | "
              f"状态: {status}")

        self.last_frame_time = current_time

    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
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

