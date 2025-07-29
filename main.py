import time
import threading

from modules.world_simulator import World
from modules.physiological_model import Physiology
from modules.psychological_model import Psychology
from modules.memory_manager import Memory
from modules.scheduler import Scheduler
from modules.autonomous_agent import Agent

class Amaya:
    def __init__(self):
        self.world = World()
        self.physiology = Physiology()
        self.psychology = Psychology()
        self.memory = Memory()
        self.scheduler = Scheduler()
        self.agent = Agent(self.world, self.physiology, self.psychology, self.memory)
        
        self.is_running = True
        self.last_checked_minute = -1
        self.tick_thread = threading.Thread(target=self.run_simulation)

    def run_simulation(self):
        """此函数在单独的线程中运行，以与真实时间同步。"""
        while self.is_running:
            self.world.tick()
            current_minute = self.world.current_time.minute
            self.physiology.tick(current_minute)

            if current_minute != self.last_checked_minute:
                current_hm = self.world.current_time.strftime("%H:%M")
                task = self.scheduler.get_task_for_time(current_hm)
                if task:
                    print(f"\n[计划任务于 {current_hm}] {task}\n", flush=True)
                    self.memory.add_memory(f"内部想法: {task}")
                self.last_checked_minute = current_minute

            time.sleep(1)

    def start(self):
        self.tick_thread.start()
        print("Amaya 已开始运行。输入 'quit' 退出。")
        print("你可以在下方与她互动。")
        self.print_status()

    def stop(self):
        self.is_running = False
        self.tick_thread.join()
        print("Amaya 已关闭。")

    def print_status(self):
        print("\n--- Amaya 当前状态 ---")
        print(self.world.get_status())
        print(self.physiology.get_status())
        print(self.psychology.get_status())
        print(self.memory.get_status())
        print("------------------------------\n", flush=True)

def main():
    amaya = Amaya()
    amaya.start()

    try:
        while True:
            user_input = input("你: ")
            if user_input.lower() == 'quit':
                break
            if user_input.lower() == 'status':
                amaya.print_status()
                continue

            # generate_response 现在返回一个消息列表或 None
            response_messages = amaya.agent.generate_response(user_input)

            if response_messages is None:
                # 模型决定不回复，可以打印一个提示或什么都不做
                print("(Amaya 看到你的消息，但暂时没有回复...)")
                continue

            # 模拟逐条发送消息的行为
            for message in response_messages:
                delay = message.get("delay seconds", 1)
                content = message.get("content", "...")
                
                # 模拟思考/打字延迟
                time.sleep(delay)
                print(f"Amaya: {content}")

    finally:
        amaya.stop()

if __name__ == "__main__":
    main()