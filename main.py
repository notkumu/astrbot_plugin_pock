from astrbot.api.all import *
import random
import requests
import os
import time


@register("poke_monitor", "Your Name", "监控戳一戳事件插件", "1.0.0")
class PokeMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 用于记录每个用户的戳一戳时间戳，键为用户 ID，值为时间戳列表
        self.user_poke_timestamps = {}
        # 定义不同戳次数对应的回复
        self.poke_responses = [
            "别戳啦！",
            "哎呀，还戳呀，别闹啦！",
            "别戳我啦,你要做什么,不理你了"
        ]

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        message_obj = event.message_obj
        raw_message = message_obj.raw_message
        is_super_double = False  # 新增标志变量，用于判断是否触发超级加倍

        if raw_message.get('post_type') == 'notice' and \
                raw_message.get('notice_type') == 'notify' and \
                raw_message.get('sub_type') == 'poke':
            bot_id = raw_message.get('self_id')
            sender_id = raw_message.get('user_id')
            target_id = raw_message.get('target_id')

            now = time.time()
            three_minutes_ago = now - 3 * 60

            # 清理该用户 3 分钟前的戳一戳记录
            if sender_id in self.user_poke_timestamps:
                self.user_poke_timestamps[sender_id] = [
                    t for t in self.user_poke_timestamps[sender_id] if t > three_minutes_ago
                ]

            if bot_id and sender_id and target_id:
                if target_id == bot_id:
                    # 记录该用户本次被戳的时间戳
                    if sender_id not in self.user_poke_timestamps:
                        self.user_poke_timestamps[sender_id] = []
                    self.user_poke_timestamps[sender_id].append(now)

                    # 获取戳的次数
                    poke_count = len(self.user_poke_timestamps[sender_id])

                    # 如果戳的次数小于 3，根据次数选择回复并输出
                    if poke_count < 3:
                        if poke_count <= len(self.poke_responses):
                            response = self.poke_responses[poke_count - 1]
                        else:
                            response = self.poke_responses[-1]
                        yield event.plain_result(response)

                    # 30% 概率决定是否戳回去
                    if random.random() < 0.3:
                        # 判断是否触发超级加倍
                        if random.random() < 0.1:
                            poke_times = 10
                            yield event.plain_result("喜欢戳是吧")
                            is_super_double = True  # 触发超级加倍，设置标志为 True
                        else:
                            poke_times = 1
                            yield event.plain_result("戳回去")

                        # 发送戳一戳请求
                        if event.get_platform_name() == "aiocqhttp":
                            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                            assert isinstance(event, AiocqhttpMessageEvent)
                            client = event.bot  # 得到 client
                            group_id = raw_message.get('group_id')
                            payloads = {
                                "user_id": sender_id
                            }
                            if group_id:
                                payloads["group_id"] = group_id
                            for _ in range(poke_times):
                                try:
                                    await client.api.call_action('send_poke', **payloads)
                                except Exception:
                                    pass

                else:
                    # 如果没有触发超级加倍，才进行表情包逻辑处理
                    if not is_super_double:
                        # 定义可选的表情包类型
                        available_actions = ["咬", "捣", "玩", "拍", "丢", "撕", "爬"]
                        # 随机选择一个动作
                        selected_action = random.choice(available_actions)

                        # 模拟调用表情包制作逻辑
                        url_mapping = {
                            "咬": "https://api.lolimi.cn/API/face_suck/api.php",
                            "捣": "https://api.lolimi.cn/API/face_pound/api.php",
                            "玩": "https://api.lolimi.cn/API/face_play/api.php",
                            "拍": "https://api.lolimi.cn/API/face_pat/api.php",
                            "丢": "https://api.lolimi.cn/API/diu/api.php",
                            "撕": "https://api.lolimi.cn/API/si/api.php",
                            "爬": "https://api.lolimi.cn/API/pa/api.php"
                        }
                        url = url_mapping.get(selected_action)
                        params = {
                            'QQ': target_id
                        }
                        try:
                            response = requests.get(url, params=params)
                            if response.status_code == 200:
                                image_data = response.content
                                # 确保保存图片的目录存在
                                save_dir = './data/plugins/poke_monitor'
                                if not os.path.exists(save_dir):
                                    os.makedirs(save_dir)
                                image_path = f"{save_dir}/{selected_action}_{target_id}.gif"
                                with open(image_path, "wb") as file:
                                    file.write(image_data)
                                yield event.image_result(image_path)
                            else:
                                yield event.plain_result(f"请求 {selected_action} 表情包失败，状态码: {response.status_code}")
                        except Exception as e:
                            yield event.plain_result(f"请求 {selected_action} 表情包时出现错误: {str(e)}")
            else:
                yield event.plain_result(f"触发了戳一戳事件，但未获取到完整信息")
