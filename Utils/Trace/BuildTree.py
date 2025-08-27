import json
import bisect
import time
from loguru import logger

class Data():
    def __init__(self, event_name, event_consumption, event_start, event_end, event_level):
        self.event_name = event_name
        self.event_consumption = event_consumption
        self.event_start = event_start
        self.event_end = event_end
        self.event_level = event_level


class UtraceTreeNode():
    def __init__(self, data, children=None, parent=None):
        self.data = data
        self.children = children or []
        self.parent = parent
        if parent:
            self.path = parent.path.copy()
            self.path.append(data.event_name)
        else:
            self.path = [data.event_name]

    def add_child(self, data):
        new_child = UtraceTreeNode(data, parent=self)
        self.children.append(new_child)
        return new_child

    def to_dict(self):
        return {
            "name": self.data.event_name,
            "consumption": self.data.event_consumption,
            "path": self.path,
            "children": [child.to_dict() for child in self.children]
        }


class UtraceHelper():
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.sorted_data = []
        self.leveled_data = {}
        self.all_frame = []

    def prepare_all_frame(self):
        current = None
        with open(self.csv_path, mode='r', encoding='utf-8') as f:
            try:
                for line in f:
                    EventName = line.strip().split(',')[3]
                    line = line.strip()
                    if EventName == "FEngineLoop::Tick":
                        if current is not None:
                            self.all_frame.append(current)
                        current = [line]
                    else:
                        if current is not None:
                            current.append(line)
                if current is not None:
                    self.all_frame.append(current)
            except Exception as e:
                print(e)

    def handle_single_frame(self, single_frame_info):
        raw_data = []
        for line in single_frame_info:
            if line.startswith("ThreadID"):
                continue
            try:
                line_li = line.strip().split(',')
                event_dict = {}
                event_dict["event_name"] = line_li[3]
                event_dict["event_start"] = float(line_li[4])
                event_dict["event_end"] = float(line_li[5])
                event_dict["event_duration"] = float(line_li[6])
                event_dict["event_depth"] = int(line_li[7])
                if event_dict.get("event_name",None):
                    raw_data.append(event_dict)
                else:
                    event_dict = {}
                    event_dict["event_name"] = "Frame"
                    event_dict["event_start"] = float(line_li[4])
                    event_dict["event_end"] = float(line_li[5])
                    event_dict["event_duration"] = float(line_li[6])
                    event_dict["event_depth"] = int(line_li[7])
                    raw_data.append(event_dict)
            except Exception as e:
                pass
        self.sorted_data = sorted(
            raw_data,
            key=lambda x:(x['event_depth'],x['event_start'])
        )

        max_depth = self.sorted_data[-1].get('event_depth') + 1
        for i in range(max_depth):
            self.leveled_data[i] =[]
        for i in self.sorted_data:
            level = i.get("event_depth")
            self.leveled_data[level].append(i)

    def build_tree(self):
        if not self.leveled_data:
            return None
        max_depth = max(self.leveled_data.keys())
        root_event = self.leveled_data[0][0]
        root_data = Data(
            root_event['event_name'],
            root_event['event_duration'],
            root_event['event_start'],
            root_event['event_end'],
            root_event['event_depth']
        )
        root_node = UtraceTreeNode(root_data)
        current_nodes = [root_node]

        for current_level in range(max_depth):
            next_level = current_level + 1
            if next_level not in self.leveled_data:
                break
            next_events = self.leveled_data[next_level]
            next_nodes = []
            starts = [event['event_start'] for event in next_events]
            for father_node in current_nodes:
                father_start = father_node.data.event_start
                father_end = father_node.data.event_end

                left_idx = bisect.bisect_left(starts, father_start)
                right_idx = bisect.bisect_right(starts, father_end)

                for i in range(left_idx, right_idx):
                    child_event = next_events[i]
                    child_end = child_event['event_end']
                    if child_end < father_end:
                        child_data = Data(
                            child_event['event_name'],
                            child_event['event_duration'],
                            child_event['event_start'],
                            child_event['event_end'],
                            child_event['event_depth']
                        )
                        child_node = father_node.add_child(child_data)
                        next_nodes.append(child_node)
            current_nodes = next_nodes
        self.leveled_data = {}
        return root_node

def run(file_path):
    helper = UtraceHelper(csv_path=file_path)
    helper.prepare_all_frame()
    cnt = 1
    for single_frame in helper.all_frame:
        try:
            helper.handle_single_frame(single_frame)
            T = helper.build_tree()
            node = T.to_dict()
            print(json.dumps(node, indent=4))
            logger.info(f"handle:{cnt}fps")
            cnt = cnt + 1
            time.sleep(0.5)
            # break
        except Exception as e:
            print(e)
if __name__ == '__main__':
    path = r'C:\Users\75251\Desktop\utrace\Trace\UE55Timer.csv'
    run(path)