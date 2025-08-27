from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Iterator, Callable
from .TreeNode import TreeNode

class ITimerNameProcessor(ABC):
    """TimerName处理器接口"""

    @abstractmethod
    def process_timer_name(self, timer_name: str, timer_id: int, depth: int) -> str:
        """
        处理TimerName

        Args:
            timer_name: 原始TimerName
            timer_id: TimerID
            depth: 调用深度

        Returns:
            处理后的TimerName
        """
        pass

    @abstractmethod
    def extract_metadata(self, timer_name: str, timer_id: int) -> Dict[str, Any]:
        """
        从TimerName中提取元数据

        Args:
            timer_name: TimerName
            timer_id: TimerID

        Returns:
            提取的元数据字典
        """
        pass


class INodeProcessor(ABC):
    """节点处理器接口"""

    @abstractmethod
    def should_include_node(self, node: TreeNode) -> bool:
        """
        判断是否应该包含此节点

        Args:
            node: 树节点

        Returns:
            是否包含此节点
        """
        pass

    @abstractmethod
    def process_node(self, node: TreeNode) -> TreeNode:
        """
        处理节点

        Args:
            node: 原始节点

        Returns:
            处理后的节点
        """
        pass


class IFrameProcessor(ABC):
    """帧处理器接口"""

    @abstractmethod
    def should_include_frame(self, frame_root: TreeNode, frame_index: int) -> bool:
        """
        判断是否应该包含此帧

        Args:
            frame_root: 帧的根节点
            frame_index: 帧索引

        Returns:
            是否包含此帧
        """
        pass

    @abstractmethod
    def process_frame(self, frame_root: TreeNode, frame_index: int) -> TreeNode:
        """
        处理整个帧

        Args:
            frame_root: 帧的根节点
            frame_index: 帧索引

        Returns:
            处理后的帧根节点
        """
        pass
