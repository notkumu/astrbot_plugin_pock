from astrbot.api.all import *
import random
import requests
import os
import time
import shutil
import yaml

@register("poke_monitor", "Your Name", "监控戳一戳事件插件", "1.3.0")
class PokeMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_poke_timestamps = {}
        # 构建配置文件路径
        config_dir = os.path.join("data", "plugins", "astrbot_plugin_pock")
        config_path = os.path.join(config_dir, "config.yml")

        # 检查配置文件是否存在，若不存在则创建并写入默认值
        if not os.path.exists(config_path):
            self._create_default_config(config_path)

        try:
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 配置文件校验
            required_sections = ['response_templates', 'emoji_url_mapping', 'blocked_users']
            for section in required_sections:
                if section not in self.config:
                    raise ValueError(f'配置文件缺少必要配置项：{section}')
            
            if not isinstance(self.config.get('blocked_users', []), list):
                raise TypeError('黑名单配置项格式错误，应为列表类型')
            
            self.response_templates = self.config['response_templates']
            self.emoji_url_mapping = self.config['emoji_url_mapping']
            self.emoji_trigger = self.config.get('emoji_trigger', {})
            self.cooldown_settings = self.config.get('cooldown_settings', {})
            self.feature_switches = self.config.get('feature_switches', {})
            self.poke_back_probability = self.config['poke_back_probability']
            self.super_poke_probability = self.config['super_poke_probability']
        except FileNotFoundError:
            self.logger.error(f"未找到配置文件: {config_path}")
        except Exception as e:
            self.logger.error(f"读取配置文件时出错: {str(e)}")

        self._clean_legacy_directories()

    def _create_default_config(self, config_path):
        """创建默认配置文件"""
        default_config = {
            # 戳一戳回复消息
            "poke_responses": [
                "别戳啦！",
                "哎呀，还戳呀，别闹啦！",
                "别戳我啦  你要做什么  不理你了"
            ],
            # 表情包 API 映射
            "emoji_url_mapping": {
                "咬": "https://api.lolimi.cn/API/face_suck/api.php",
                "捣": "https://api.lolimi.cn/API/face_pound/api.php",
                "玩": "https://api.lolimi.cn/API/face_play/api.php",
                "拍": "https://api.lolimi.cn/API/face_pat/api.php",
                "丢": "https://api.lolimi.cn/API/diu/api.php",
                "撕": "https://api.lolimi.cn/API/si/api.php",
                "爬": "https://api.lolimi.cn/API/pa/api.php"
            },
            # 随机触发表情包的概率
            "random_emoji_trigger_probability": 0.5,
            # 功能开关
            "feature_switches": {
                "poke_response_enabled": True,
                "poke_back_enabled": True,
                "emoji_trigger_enabled": True
            },
            # 戳 Bot 反击相关概率
            "poke_back_probability": 0.3,
            "super_poke_probability": 0.1
        }
        # 创建配置文件所在目录
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
            self.logger.info(f"已创建默认配置文件: {config_path}")
        except Exception as e:
            self.logger.error(f"创建默认配置文件时出错: {str(e)}")

    def _clean_legacy_directories(self):
        """安全清理旧目录（仅删除特定目录）"""
        legacy_dirs = [
            os.path.abspath("./data/plugins/poke_monitor"),  # 旧版本目录
            os.path.abspath("./data/plugins/plugins/poke_monitor")  # 防止误删其他插件
        ]

        for path in legacy_dirs:
            try:
                if os.path.exists(path):
                    shutil.rmtree(path)
                    self.logger.info(f"已清理旧目录: {path}")
            except Exception as e:
                self.logger.error(f"清理目录 {path} 失败: {str(e)}")

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        message_obj = event.message_obj
        raw_message = message_obj.raw_message
        is_super = False  # 超级加倍标志
        
        # 黑名单校验
        sender_id = str(raw_message.get('user_id'))
        if sender_id in self.config.get('blocked_users', []):
            self.logger.info(f'已拦截黑名单用户 {sender_id} 的交互请求')
            return

        if raw_message.get('post_type') == 'notice' and \
                raw_message.get('notice_type') == 'notify' and \
                raw_message.get('sub_type') == 'poke':
            bot_id = raw_message.get('self_id')
            sender_id = raw_message.get('user_id')
            target_id = raw_message.get('target_id')

            now = time.time()
            three_minutes_ago = now - 3 * 60

            # 清理旧记录
            if sender_id in self.user_poke_timestamps:
                self.user_poke_timestamps[sender_id] = [
                    t for t in self.user_poke_timestamps[sender_id] if t > three_minutes_ago
                ]

            if bot_id and sender_id and target_id:
                # 用户戳机器人
                if str(target_id) == str(bot_id):
                    # 记录戳一戳
                    if sender_id not in self.user_poke_timestamps:
                        self.user_poke_timestamps[sender_id] = []
                    self.user_poke_timestamps[sender_id].append(now)

                    # 文本回复
                    if self.feature_switches.get('poke_response_enabled', True):
                        now = time.time()
                        # 冷却时间检查
                        last_interaction = self.user_interactions.get(sender_id, 0)
                        if now - last_interaction < self.cooldown_settings.get('user_specific_cooldown', 30):
                            return
                        
                        poke_count = len(self.user_poke_timestamps[sender_id])
                        # 动态选择回复模板
                        if poke_count <= 2:
                            responses = self.response_templates.get('initial_responses', [])
                        else:
                            responses = self.response_templates.get('persistent_responses', [])
                        
                        if responses:
                            response = random.choice(responses)
                            self.user_interactions[sender_id] = now
                            yield event.plain_result(response)

                    # 概率戳回
                    if self.feature_switches.get('poke_back_enabled', True) and random.random() < self.poke_back_probability:
                        if random.random() < self.super_poke_probability:
                            poke_times = 10
                            yield event.plain_result("喜欢戳是吧")
                            is_super = True
                        else:
                            poke_times = 1
                            yield event.plain_result("戳回去")

                        # 发送戳一戳
                        if event.get_platform_name() == "aiocqhttp":
                            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                            assert isinstance(event, AiocqhttpMessageEvent)
                            client = event.bot
                            group_id = raw_message.get('group_id')
                            payloads = {"user_id": sender_id}
                            if group_id:
                                payloads["group_id"] = group_id
                            for _ in range(poke_times):
                                try:
                                    await client.api.call_action('send_poke', **payloads)
                                except Exception as e:
                                    self.logger.error(f"发送戳一戳失败: {str(e)}")

                # 用户戳其他人（且不是机器人自己触发的）
                elif str(sender_id) != str(bot_id):  
                    # 随机触发表情包
                    if self.feature_switches.get('emoji_trigger_enabled', True):
                        # 动态概率计算
                        current_hour = time.localtime().tm_hour
                        base_prob = self.emoji_trigger.get('base_probability', 0.5)
                        
                        # 时段调整
                        if current_hour in self.emoji_trigger.get('time_based_adjustments', {}).get('night_hours', []):
                            base_prob *= self.emoji_trigger['time_based_adjustments'].get('probability_multiplier', 1.0)
                        
                        # 用户关系调整
                        user_interact_count = len(self.user_interactions.get(sender_id, []))
                        if user_interact_count > 10:
                            base_prob *= self.emoji_trigger.get('user_relationship', {}).get('familiar_user_boost', 1.0)
                        elif user_interact_count < 3:
                            base_prob *= self.emoji_trigger.get('user_relationship', {}).get('new_user_penalty', 1.0)
                        
                        # 连续触发衰减
                        consecutive_triggers = self.user_poke_timestamps.get(sender_id, [])
                        decay_factor = self.emoji_trigger.get('consecutive_trigger', {}).get('decay_factor', 1.0)
                        adjusted_prob = base_prob * (decay_factor ** len(consecutive_triggers))
                        
                        if random.random() < adjusted_prob:
                        available_actions = list(self.emoji_url_mapping.keys())
                        selected_action = random.choice(available_actions)

                        url = self.emoji_url_mapping.get(selected_action)
                        params = {
                            'QQ': target_id,
                            'type': 'json' if self.config.get('use_json_api', False) else 'image'
                        }

                        # 硬编码请求配置
                        timeout = 10
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                try:
                            response = requests.get(url, params=params, timeout=5)
                            response.raise_for_status()
                            image = response.content
                            self.logger.info(f"成功获取表情包：{url}")
                        except Exception as e:
                            self.logger.error(f"获取表情包失败：{str(e)}")
                            return
                                if response.status_code == 200:
                                    # 跨平台安全路径
                                    save_dir = os.path.join("data", "plugins", "astrbot_plugin_pock", "poke_monitor")
                                    os.makedirs(save_dir, exist_ok=True)

                                    # 唯一文件名防止冲突
                                    filename = f"{selected_action}_{target_id}_{int(time.time())}.gif"
                                    image_path = os.path.join(save_dir, filename)

                                    with open(image_path, "wb") as f:
                                        f.write(response.content)
                                    yield event.image_result(image_path)
                                    break
                                else:
                                    yield event.plain_result(f"表情包请求失败，状态码：{response.status_code}")
                                    break
                            except requests.exceptions.ReadTimeout:
                                retry_count += 1
                                if retry_count == max_retries:
                                    yield event.plain_result(f"表情包处理出错：多次请求超时，无法获取数据。")
                            except Exception as e:
                                yield event.plain_result(f"表情包处理出错：{str(e)}")
                                break
