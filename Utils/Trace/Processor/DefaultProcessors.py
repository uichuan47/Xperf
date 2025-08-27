from typing import List, Dict, Any, Optional, Iterator, Callable
from .TreeNode import TreeNode
from .BaseProcessors import INodeProcessor,IFrameProcessor,ITimerNameProcessor
import re
class DefaultTimerNameProcessor(ITimerNameProcessor):
    """默认的TimerName处理器"""

    def __init__(self):
        # 预定义的处理规则
        self.cleanup_patterns = [
            (r'^STAT_', ''),  # 移除STAT_前缀
            (r'_+', '_'),  # 多个下划线替换为单个
            (r'^_|_$', ''),  # 移除开头和结尾的下划线
        ]

        # 分类规则
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
        """处理TimerName"""
        processed_name = timer_name

        # # 应用清理规则
        # for pattern, replacement in self.cleanup_patterns:
        #     processed_name = re.sub(pattern, replacement, processed_name)
        if processed_name == '':
            processed_name = "FrameKento"
        return processed_name

    def extract_metadata(self, timer_name: str, timer_id: int) -> Dict[str, Any]:
        """提取元数据"""
        metadata = {}

        # # 分类
        # category = 'Other'
        # for cat, patterns in self.category_patterns.items():
        #     if any(re.match(pattern, timer_name, re.IGNORECASE) for pattern in patterns):
        #         category = cat
        #         break
        #
        # metadata['category'] = category
        #
        # # 提取数值信息（如果TimerName中包含数字）
        # numbers = re.findall(r'\d+', timer_name)
        # if numbers:
        #     metadata['numbers'] = [int(n) for n in numbers]
        #
        # # 检查是否是统计相关
        # metadata['is_stat'] = timer_name.startswith('STAT_')

        return metadata


class DefaultNodeProcessor(INodeProcessor):
    """默认的节点处理器"""

    def __init__(self, min_duration: float = 0.0, exclude_categories: List[str] = None):
        self.min_duration = min_duration
        self.exclude_categories = exclude_categories or []

    def should_include_node(self, node: TreeNode) -> bool:
        """判断是否包含节点"""
        # # 过滤掉持续时间太短的节点
        # if node.duration < self.min_duration:
        #     return False
        #
        # # 过滤掉特定分类的节点
        # if 'category' in node.metadata:
        #     if node.metadata['category'] in self.exclude_categories:
        #         return False

        return True

    def process_node(self, node: TreeNode) -> TreeNode:
        """处理节点"""
        # 可以在这里添加额外的节点处理逻辑
        # 例如：计算相对时间、添加性能标记等

        # if node.duration > 0.01:  # 10ms
        #     node.metadata['performance_level'] = 'slow'
        # elif node.duration > 0.001:  # 1ms
        #     node.metadata['performance_level'] = 'normal'
        # else:
        #     node.metadata['performance_level'] = 'fast'

        return node


class DefaultFrameProcessor(IFrameProcessor):
    """默认的帧处理器"""

    def __init__(self, min_frame_duration: float = 0.0, max_frame_count: int = None):
        self.min_frame_duration = min_frame_duration
        self.max_frame_count = max_frame_count

    def should_include_frame(self, frame_root: TreeNode, frame_index: int) -> bool:
        """判断是否包含帧"""
        # 限制最大帧数
        # if self.max_frame_count and frame_index > self.max_frame_count:
        #     return False
        #
        # # 过滤掉持续时间太短的帧
        # if frame_root.duration < self.min_frame_duration:
        #     return False

        return True

    def process_frame(self, frame_root: TreeNode, frame_index: int) -> TreeNode:
        """处理帧"""
        # 添加帧级别的元数据
        # frame_root.metadata['frame_index'] = frame_index
        # frame_root.metadata['fps'] = 1.0 / frame_root.duration if frame_root.duration > 0 else 0
        #
        # # 计算帧的性能等级
        # if frame_root.duration > 0.033:  # 30 FPS
        #     frame_root.metadata['frame_performance'] = 'poor'
        # elif frame_root.duration > 0.016:  # 60 FPS
        #     frame_root.metadata['frame_performance'] = 'acceptable'
        # else:
        #     frame_root.metadata['frame_performance'] = 'good'

        return frame_root