from typing import List, Dict, Any, Optional, Iterator, Callable
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
        self.metadata: Dict[str, Any] = {}  # 用于存储额外的处理结果

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

        # 如果有元数据，也包含进去
        if self.metadata:
            result["metadata"] = self.metadata

        return result
