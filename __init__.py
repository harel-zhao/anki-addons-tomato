# Copyright: 2025
# License: GNU GPL, version 3 or later

"""
番茄钟插件 (Tomato Timer)
在Anki复习界面右侧显示番茄钟倒计时
左侧显示卡片复习统计
"""

from aqt import mw, gui_hooks
from aqt.qt import *
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# 插件版本
__version__ = "1.4.2"

# 日志文件
log_file = Path(__file__).parent / "tomato_timer_log.txt"

def log(message):
    """记录日志"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
        print(log_line)
    except Exception as e:
        print(f"日志错误: {e}")

log("=" * 50)
log("番茄钟插件开始加载")

# 配置
config_file = Path(__file__).parent / "config.json"
default_config = {
    "work_minutes": 25,
    "break_minutes": 5,
    "auto_start": False,
    "sound_enabled": True,
    "widget_enabled": True,
    "card_review_count": {
        "enabled": True,
        "show_correct_rate": True,
        "master_threshold": 3,
        "master_recent_count": 3,
        "use_green_for_mastered": True,
        "default_color": "#e74c3c",
        "mastered_color": "#27ae60",
        "widget_enabled": True
    }
}

def load_config():
    """加载配置"""
    try:
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
            for key in default_config:
                if key not in config:
                    config[key] = default_config[key]
                elif isinstance(default_config[key], dict) and isinstance(config.get(key), dict):
                    for subkey in default_config[key]:
                        if subkey not in config[key]:
                            config[key][subkey] = default_config[key][subkey]
            return config
        return default_config
    except Exception as e:
        log(f"加载配置失败: {e}")
        return default_config

def save_config():
    """保存配置"""
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log(f"保存配置失败: {e}")
        return False

# 全局变量
config = load_config()
timer_widget = None
dock_widget = None
review_count_widget = None
review_count_dock = None
session_stats = None

# ============================================================================
# 本地数据库管理
# ============================================================================

def init_db():
    """初始化数据库"""
    db_file = Path(__file__).parent / "tomato_timer.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 创建番茄钟统计表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pomodoro_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            count INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()
    log("数据库初始化完成")

def get_today_pomodoro_count():
    """获取今日番茄钟数量"""
    db_file = Path(__file__).parent / "tomato_timer.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute(
        "SELECT count FROM pomodoro_stats WHERE date = ?",
        (today,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 0

def increment_pomodoro_count():
    """增加今日番茄钟数量"""
    db_file = Path(__file__).parent / "tomato_timer.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute("""
        INSERT INTO pomodoro_stats (date, count) VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET count = count + 1
    """, (today,))
    
    conn.commit()
    conn.close()
    log(f"番茄钟计数+1")

# ============================================================================
# 会话统计类
# ============================================================================

class SessionStats:
    """会话统计"""
    
    def __init__(self):
        self.total = 0
        self.correct = 0
    
    def add_answer(self, ease):
        """添加回答"""
        self.total += 1
        if ease and ease >= 3:  # 3=好，4=轻松
            self.correct += 1
    
    def get_rate(self):
        """获取正确率"""
        if self.total == 0:
            return 0
        return int(self.correct / self.total * 100)
    
    def reset(self):
        """重置统计"""
        self.total = 0
        self.correct = 0

# ============================================================================
# 卡片复习统计Widget
# ============================================================================

class CardReviewCountWidget(QWidget):
    """卡片复习统计显示部件"""
    
    def __init__(self):
        super().__init__()
        self.current_card = None
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        log("设置卡片统计UI...")
        
        layout = QVBoxLayout()
        
        # 复习次数显示（大字体）
        self.count_label = QLabel("1")
        self.count_label.setStyleSheet("font-size: 48px; font-weight: bold; color: #e74c3c; font-family: Arial, sans-serif; text-align: center;")
        layout.addWidget(self.count_label)
        
        # "复习"标签（小字体）
        self.count_subtitle = QLabel("复习")
        self.count_subtitle.setStyleSheet("font-size: 14px; color: #7f8c8d; margin-bottom: 10px; text-align: center;")
        layout.addWidget(self.count_subtitle)
        
        # 间隔
        layout.addSpacing(10)
        
        # 正确率显示（中字体）
        self.rate_label = QLabel("0%")
        self.rate_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #34495e; text-align: center;")
        layout.addWidget(self.rate_label)
        
        # "正确率"标签（小字体）
        self.rate_subtitle = QLabel("正确率")
        self.rate_subtitle.setStyleSheet("font-size: 12px; color: #7f8c8d; text-align: center;")
        layout.addWidget(self.rate_subtitle)
        
        layout.addStretch()
        self.setLayout(layout)
        
        log("卡片统计UI设置完成")
    
    def update_card(self, card):
        """更新卡片信息"""
        self.current_card = card

        # 获取配置
        card_config = config.get('card_review_count', {})

        # 检查widget是否启用
        if not card_config.get('widget_enabled', True):
            self.hide_all()
            return

        # 检查是否启用
        if not card_config.get('enabled', True):
            self.hide_all()
            return

        # 获取复习次数和是否新卡
        review_count, is_new = self.get_review_count(card)

        if is_new:
            # 新卡片显示"新"
            log(f"新卡片: {card.id}, 设置为红色")
            self.count_label.setText("新")
            self.count_label.setStyleSheet("font-size: 48px; font-weight: bold; color: #e74c3c; font-family: Arial, sans-serif; text-align: center;")
            self.count_subtitle.setText("新卡片")
            # 新卡片不显示正确率
            self.count_label.show()
            self.count_subtitle.show()
            self.rate_label.hide()
            self.rate_subtitle.hide()
        else:
            # 已复习卡片显示次数和颜色
            log(f"已复习卡片: {card.id}, 复习次数: {review_count}")
            if self.should_show_green(card, review_count, card_config):
                color = card_config.get('mastered_color', '#27ae60')
            else:
                color = card_config.get('default_color', '#e74c3c')

            self.count_label.setText(str(review_count))
            self.count_label.setStyleSheet(f"font-size: 48px; font-weight: bold; color: {color}; font-family: Arial, sans-serif; text-align: center;")
            self.count_subtitle.setText("复习")

            # 显示正确率
            if card_config.get('show_correct_rate', True):
                global session_stats
                if session_stats:
                    rate = session_stats.get_rate()
                    self.rate_label.setText(f"{rate}%")
                else:
                    self.rate_label.setText("0%")
                self.show_all()
            else:
                # 不显示正确率
                self.show_count_only()
    
    def update_correct_rate(self, rate):
        """更新正确率"""
        card_config = config.get('card_review_count', {})
        
        if card_config.get('show_correct_rate', True):
            self.rate_label.setText(f"{rate}%")
            self.show_all()
        else:
            self.hide_rate()
    
    def get_review_count(self, card):
        """获取卡片复习次数，返回 (次数, 是否新卡)"""
        try:
            if not card or not mw.col:
                return (1, True)

            count = mw.col.db.scalar(
                "SELECT COUNT(*) FROM revlog WHERE cid = ?",
                card.id
            )
            if count == 0:
                return (0, True)
            else:
                return (count, False)
        except Exception as e:
            log(f"获取复习次数失败: {e}")
            return (1, True)
    
    def is_mastered(self, card):
        """判断卡片是否熟练掌握"""
        try:
            if not card or not mw.col:
                return False
            
            card_config = config.get('card_review_count', {})
            master_recent_count = card_config.get('master_recent_count', 3)
            
            # 获取最近N次的回答
            recent_eases = mw.col.db.list(
                f"SELECT ease FROM revlog WHERE cid = ? ORDER BY id DESC LIMIT {master_recent_count}",
                card.id
            )
            
            # 检查是否都是"轻松"（ease=4）
            if len(recent_eases) < master_recent_count:
                return False
            
            return all(ease == 4 for ease in recent_eases)
        except Exception as e:
            log(f"判断掌握状态失败: {e}")
            return False
    
    def should_show_green(self, card, review_count, card_config):
        """判断是否显示绿色"""
        # 检查是否启用绿色
        if not card_config.get('use_green_for_mastered', True):
            return False
        
        # 检查复习次数阈值
        master_threshold = card_config.get('master_threshold', 3)
        if review_count < master_threshold:
            return False
        
        # 检查是否熟练掌握
        return self.is_mastered(card)
    
    def show_all(self):
        """显示所有元素"""
        self.count_label.show()
        self.count_subtitle.show()
        self.rate_label.show()
        self.rate_subtitle.show()
    
    def hide_rate(self):
        """隐藏正确率"""
        self.rate_label.hide()
        self.rate_subtitle.show()

    def show_count_only(self):
        """只显示复习次数"""
        self.count_label.show()
        self.count_subtitle.show()
        self.rate_label.hide()
        self.rate_subtitle.hide()

    def hide_all(self):
        """隐藏所有元素"""
        self.count_label.hide()
        self.count_subtitle.hide()
        self.rate_label.hide()
        self.rate_subtitle.hide()

# ============================================================================
# 番茄钟Widget
# ============================================================================

class TomatoTimerWidget(QWidget):
    """番茄钟窗口部件"""
    
    def __init__(self):
        super().__init__()
        self.timer = None
        self.start_time = None
        self.elapsed_time = 0
        self.is_running = False
        self.is_work_mode = True
        self.pomodoro_count = 0
        
        self.setup_ui()
        self.load_pomodoro_count()
    
    def setup_ui(self):
        """设置UI"""
        log("设置UI...")
        
        layout = QVBoxLayout()
        
        # 标题
        self.title_label = QLabel("🧠 专注时间")
        self.title_label.setStyleSheet("font-size: 14px; color: #7f8c8d; margin-bottom: 10px;")
        layout.addWidget(self.title_label)
        
        # 时间显示
        self.time_label = QLabel(f"{config['work_minutes']:02d}:00")
        self.time_label.setStyleSheet("font-size: 36px; font-weight: bold; color: #e74c3c; font-family: Courier New;")
        layout.addWidget(self.time_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #ecf0f1;
                border-radius: 3px;
                height: 8px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e74c3c, stop:1 #c0392b);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("▶️ 开始")
        self.start_button.clicked.connect(self.toggle_timer)
        self.start_button.setStyleSheet("""
            QPushButton {
                    background: #2ecc71;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 13px;
                }
            QPushButton:hover {
                    background: #27ae60;
                }
        """)
        button_layout.addWidget(self.start_button)
        
        self.reset_button = QPushButton("🔄 重置")
        self.reset_button.clicked.connect(self.reset_timer)
        self.reset_button.setStyleSheet("""
            QPushButton {
                    background: #95a5a6;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 13px;
                }
            QPushButton:hover {
                    background: #7f8c8d;
                }
        """)
        button_layout.addWidget(self.reset_button)
        
        layout.addLayout(button_layout)
        
        # 统计
        self.stats_label = QLabel(f"今日番茄钟: {self.pomodoro_count} 个")
        self.stats_label.setStyleSheet("font-size: 12px; color: #7f8c8d; margin-top: 15px; padding: 10px; background: #f8f9fa; border-radius: 5px;")
        layout.addWidget(self.stats_label)
        
        layout.addStretch()
        self.setLayout(layout)
        
        log("UI设置完成")
    
    def toggle_timer(self):
        """切换计时器"""
        if self.is_running:
            self.pause_timer()
        else:
            self.start_timer()
    
    def start_timer(self):
        """开始计时"""
        log("开始计时")
        if not self.start_time:
            self.start_time = time.time() - self.elapsed_time
        self.is_running = True
        
        if not self.timer:
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_timer)
        
        self.timer.start(1000)
        self.update_button_state()
    
    def pause_timer(self):
        """暂停计时"""
        log("暂停计时")
        self.elapsed_time = time.time() - self.start_time
        self.is_running = False
        if self.timer:
            self.timer.stop()
        self.update_button_state()
    
    def reset_timer(self):
        """重置计时器"""
        log("重置计时器")
        if self.timer:
            self.timer.stop()
        self.start_time = None
        self.elapsed_time = 0
        self.is_running = False
        self.update_display()
        self.update_button_state()
    
    def update_timer(self):
        """更新计时器"""
        if not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        total_seconds = config['work_minutes'] * 60 if self.is_work_mode else config['break_minutes'] * 60
        remaining = total_seconds - elapsed
        
        if remaining <= 0:
            self.on_timer_complete()
            return
        
        # 更新显示
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.progress_bar.setValue(int((remaining / total_seconds) * 100))
    
    def on_timer_complete(self):
        """计时完成"""
        log("计时完成！")
        if self.timer:
            self.timer.stop()
        
        self.start_time = None
        self.elapsed_time = 0
        
        # 播放提示音
        if config.get('sound_enabled', True):
            QApplication.beep()
        
        # 切换模式
        if self.is_work_mode:
            self.is_work_mode = False
            self.pomodoro_count += 1
            increment_pomodoro_count()
            self.update_mode_ui()
            log("切换到休息模式")
        else:
            self.is_work_mode = True
            self.update_mode_ui()
            log("切换到工作模式")
        
        self.update_display()
        self.update_button_state()
    
    def update_mode_ui(self):
        """更新工作/休息模式UI"""
        if self.is_work_mode:
            self.title_label.setText("🧠 专注时间")
            self.time_label.setStyleSheet("font-size: 36px; font-weight: bold; color: #e74c3c; font-family: Courier New;")
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                        border: none;
                        background: #ecf0f1;
                        border-radius: 3px;
                        height: 8px;
                    }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e74c3c, stop:1 #c0392b);
                    border-radius: 3px;
                }
            """)
        else:
            self.title_label.setText("☕ 休息时间")
            self.time_label.setStyleSheet("font-size: 36px; font-weight: bold; color: #27ae60; font-family: Courier New;")
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                        border: none;
                        background: #ecf0f1;
                        border-radius: 3px;
                        height: 8px;
                    }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #27ae60, stop:1 #2ecc71);
                    border-radius: 3px;
                }
            """)
        
        # 更新统计
        today_count = get_today_pomodoro_count()
        self.stats_label.setText(f"今日番茄钟: {today_count} 个")
    
    def update_display(self):
        """更新显示"""
        total_seconds = config['work_minutes'] * 60 if self.is_work_mode else config['break_minutes'] * 60
        minutes = total_seconds // 60
        self.time_label.setText(f"{minutes:02d}:00")
        self.progress_bar.setValue(100)
    
    def update_button_state(self):
        """更新按钮状态"""
        if self.is_running:
            self.start_button.setText("⏸️ 暂停")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: #f39c12;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: #e67e22;
                }
            """)
        else:
            self.start_button.setText("▶️ 开始")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background: #2ecc71;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 5px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background: #27ae60;
                }
            """)
    
    def load_pomodoro_count(self):
        """加载番茄钟计数"""
        try:
            today_count = get_today_pomodoro_count()
            self.pomodoro_count = today_count
        except Exception as e:
            log(f"加载番茄钟统计失败: {e}")
            self.pomodoro_count = 0
    

# ============================================================================
# 设置对话框
# ============================================================================

class TomatoSettingsDialog(QDialog):
    """番茄钟设置对话框"""
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙️ 番茄钟设置")
        self.setMinimumSize(400, 300)
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        
        # 番茄钟设置
        tomato_group = QGroupBox("🍅 番茄钟设置")
        tomato_layout = QVBoxLayout()
        
        # 工作时间
        work_layout = QHBoxLayout()
        work_layout.addWidget(QLabel("工作时间（分钟）:"))
        self.work_spin = QSpinBox()
        self.work_spin.setRange(1, 120)
        self.work_spin.setValue(self.config.get('work_minutes', 25))
        work_layout.addWidget(self.work_spin)
        work_layout.addStretch()
        tomato_layout.addLayout(work_layout)
        
        # 休息时间
        break_layout = QHBoxLayout()
        break_layout.addWidget(QLabel("休息时间（分钟）:"))
        self.break_spin = QSpinBox()
        self.break_spin.setRange(1, 30)
        self.break_spin.setValue(self.config.get('break_minutes', 5))
        break_layout.addWidget(self.break_spin)
        break_layout.addStretch()
        tomato_layout.addLayout(break_layout)
        
        # 自动开始
        self.auto_start_check = QCheckBox("进入复习时自动开始")
        self.auto_start_check.setChecked(self.config.get('auto_start', False))
        tomato_layout.addWidget(self.auto_start_check)
        
        # 提示音
        self.sound_check = QCheckBox("完成时播放提示音")
        self.sound_check.setChecked(self.config.get('sound_enabled', True))
        tomato_layout.addWidget(self.sound_check)
        
        tomato_group.setLayout(tomato_layout)
        layout.addWidget(tomato_group)
        
        # 卡片统计设置
        stats_group = QGroupBox("📊 卡片统计设置")
        stats_layout = QVBoxLayout()
        
        # 启用统计
        self.stats_enabled_check = QCheckBox("启用卡片复习统计")
        stats_enabled = self.config.get('card_review_count', {}).get('enabled', True)
        self.stats_enabled_check.setChecked(stats_enabled)
        stats_layout.addWidget(self.stats_enabled_check)
        
        # 显示正确率
        self.show_rate_check = QCheckBox("显示正确率")
        show_rate = self.config.get('card_review_count', {}).get('show_correct_rate', True)
        self.show_rate_check.setChecked(show_rate)
        stats_layout.addWidget(self.show_rate_check)
        
        # 掌握阈值
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(QLabel("掌握阈值（复习次数）:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10)
        self.threshold_spin.setValue(self.config.get('card_review_count', {}).get('master_threshold', 3))
        threshold_layout.addWidget(self.threshold_spin)
        threshold_layout.addStretch()
        stats_layout.addLayout(threshold_layout)
        
        # 使用绿色
        self.green_check = QCheckBox("已掌握显示绿色")
        use_green = self.config.get('card_review_count', {}).get('use_green_for_mastered', True)
        self.green_check.setChecked(use_green)
        stats_layout.addWidget(self.green_check)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        layout.addStretch()
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setMinimumHeight(35)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def save_settings(self):
        """保存设置"""
        try:
            # 更新配置
            self.config['work_minutes'] = self.work_spin.value()
            self.config['break_minutes'] = self.break_spin.value()
            self.config['auto_start'] = self.auto_start_check.isChecked()
            self.config['sound_enabled'] = self.sound_check.isChecked()
            self.config['card_review_count']['enabled'] = self.stats_enabled_check.isChecked()
            self.config['card_review_count']['show_correct_rate'] = self.show_rate_check.isChecked()
            self.config['card_review_count']['master_threshold'] = self.threshold_spin.value()
            self.config['card_review_count']['use_green_for_mastered'] = self.green_check.isChecked()
            
            # 保存配置
            from aqt import mw
            addon_name = __name__.rsplit('.', 1)[0]
            mw.addonManager.writeConfig(addon_name, self.config)
            
            QMessageBox.information(self, "设置已保存", "番茄钟设置已保存！")
            self.accept()
            
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存设置失败: {e}")

# ============================================================================
# 初始化函数
# ============================================================================

def init_plugin():
    """初始化插件"""
    global timer_widget, dock_widget, review_count_widget, review_count_dock, session_stats
    
    try:
        log("开始初始化番茄钟...")
        
        # 初始化数据库
        init_db()
        
        # 初始化会话统计
        session_stats = SessionStats()
        
        # 添加菜单项
        def show_tomato_timer():
            """显示番茄钟窗口"""
            global dock_widget, timer_widget
            try:
                if dock_widget is None:
                    log("创建新的番茄钟窗口...")
                    timer_widget = TomatoTimerWidget()
                    dock_widget = QDockWidget("🍅 番茄钟", mw)
                    dock_widget.setMinimumWidth(240)
                    dock_widget.setMaximumWidth(300)
                    dock_widget.setWidget(timer_widget)
                    
                    try:
                        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_widget)
                        log("使用PyQt6方式添加dock")
                    except:
                        try:
                            mw.addDockWidget(Qt.RightDockWidgetArea, dock_widget)
                            log("使用PyQt5方式添加dock")
                        except:
                            mw.addDockWidget(2, dock_widget)
                            log("使用数值方式添加dock")
                else:
                    dock_widget.show()
                    log("显示已存在的番茄钟窗口")
            except Exception as e:
                log(f"显示番茄钟失败: {e}")
                import traceback
                traceback.print_exc()
        
        def toggle_tomato_display():
            """切换番茄钟窗口显示"""
            global config, dock_widget
            try:
                is_enabled = config.get('widget_enabled', True)
                config['widget_enabled'] = not is_enabled
                save_config()
                
                if dock_widget:
                    if config['widget_enabled']:
                        dock_widget.show()
                        log("番茄钟窗口已显示")
                    else:
                        dock_widget.hide()
                        log("番茄钟窗口已隐藏")
            except Exception as e:
                log(f"切换番茄钟显示失败: {e}")
        
        def toggle_card_stats_display():
            """切换卡片统计窗口显示"""
            global config, review_count_dock
            try:
                card_config = config.get('card_review_count', {})
                is_enabled = card_config.get('widget_enabled', True)
                card_config['widget_enabled'] = not is_enabled
                config['card_review_count'] = card_config
                save_config()
                
                if review_count_dock:
                    if card_config['widget_enabled']:
                        review_count_dock.show()
                        log("卡片统计窗口已显示")
                    else:
                        review_count_dock.hide()
                        log("卡片统计窗口已隐藏")
            except Exception as e:
                log(f"切换卡片统计显示失败: {e}")
        
        def show_settings():
            """显示设置对话框"""
            dialog = TomatoSettingsDialog(mw, config)
            dialog.exec_()
        
        # 创建子菜单
        tomato_menu = QMenu("🍅 显示番茄钟", mw)
        
        # 显示计时器开关
        tomato_display_action = QAction("☑ 显示计时器", mw)
        tomato_display_action.setCheckable(True)
        tomato_display_action.setChecked(config.get('widget_enabled', True))
        tomato_display_action.triggered.connect(lambda: toggle_tomato_display())
        tomato_menu.addAction(tomato_display_action)
        
        # 显示卡片统计开关
        card_stats_display_action = QAction("☑ 显示卡片统计", mw)
        card_stats_display_action.setCheckable(True)
        card_stats_display_action.setChecked(config.get('card_review_count', {}).get('widget_enabled', True))
        card_stats_display_action.triggered.connect(lambda: toggle_card_stats_display())
        tomato_menu.addAction(card_stats_display_action)
        
        # 设置菜单项
        settings_action = QAction("⚙️ 番茄钟设置", mw)
        settings_action.triggered.connect(show_settings)
        
        if hasattr(mw, 'form') and hasattr(mw.form, 'menuTools'):
            mw.form.menuTools.addMenu(tomato_menu)
            mw.form.menuTools.addSeparator()
            mw.form.menuTools.addAction(settings_action)
            log("菜单已添加到工具菜单")
        else:
            mw.menuBar().addMenu(tomato_menu)
            mw.menuBar().addAction(settings_action)
            log("菜单已添加到主菜单栏")
        
        # 延迟初始化
        def delayed_init():
            try:
                log("执行延迟初始化...")
                show_tomato_timer()
                
                # 根据配置显示/隐藏番茄钟窗口
                if not config.get('widget_enabled', True):
                    if dock_widget:
                        dock_widget.hide()
                        log("番茄钟窗口初始隐藏")
                
                # 初始化卡片复习计数器
                card_config = config.get('card_review_count', {})
                if card_config.get('enabled', True):
                    init_card_review_counter()
                
                log("✅ 番茄钟初始化成功")
            except Exception as e:
                log(f"❌ 番茄钟初始化失败: {e}")
                import traceback
                traceback.print_exc()
        
        QTimer.singleShot(1000, delayed_init)
        
        log("番茄钟插件加载完成")
        
    except Exception as e:
        log(f"❌ 插件初始化失败: {e}")
        import traceback
        traceback.print_exc()

def init_card_review_counter():
    """初始化卡片复习计数器"""
    global review_count_widget, review_count_dock
    
    try:
        log("初始化卡片复习计数器...")
        
        # 创建widget
        review_count_widget = CardReviewCountWidget()
        
        # 创建dock
        review_count_dock = QDockWidget("复习统计", mw)
        review_count_dock.setMinimumWidth(140)
        review_count_dock.setMaximumWidth(150)
        review_count_dock.setWidget(review_count_widget)
        
        # 添加到左侧
        try:
            mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, review_count_dock)
            log("使用PyQt6方式添加计数器到左侧")
        except:
            try:
                mw.addDockWidget(Qt.LeftDockWidgetArea, review_count_dock)
                log("使用PyQt5方式添加计数器到左侧")
            except:
                mw.addDockWidget(1, review_count_dock)
                log("使用数值方式添加计数器到左侧")
        
        # 初始隐藏dock窗口
        review_count_dock.hide()
        
        # 根据配置隐藏卡片统计窗口
        card_config = config.get('card_review_count', {})
        if not card_config.get('widget_enabled', True):
            review_count_dock.hide()
            log("卡片统计窗口初始隐藏")
        
        # 注册hooks
        gui_hooks.reviewer_did_show_question.append(on_show_question)
        gui_hooks.reviewer_did_answer_card.append(on_answer_card)
        gui_hooks.reviewer_will_end.append(on_reviewer_end)
        
        log("✅ 卡片复习计数器初始化成功")
        
    except Exception as e:
        log(f"❌ 卡片复习计数器初始化失败: {e}")
        import traceback
        traceback.print_exc()

def on_show_question(card):
    """显示问题时"""
    global review_count_dock, review_count_widget, session_stats
    
    card_config = config.get('card_review_count', {})
    if not card_config.get('enabled', True):
        return
    
    if not card_config.get('widget_enabled', True):
        return
    
    try:
        if review_count_dock and review_count_widget:
            review_count_dock.show()
            review_count_widget.update_card(card)
    except Exception as e:
        log(f"显示卡片信息失败: {e}")

def on_answer_card(card, ease, state):
    """回答卡片后"""
    global session_stats, review_count_widget
    
    try:
        if not session_stats:
            log("session_stats 未初始化，跳过统计更新")
            return
            
        session_stats.add_answer(ease)
        
        if review_count_widget:
            rate = session_stats.get_rate()
            review_count_widget.update_correct_rate(rate)
    except Exception as e:
        log(f"更新统计失败: {e}")

def on_reviewer_end():
    """复习结束时"""
    global review_count_dock
    
    try:
        if review_count_dock:
            review_count_dock.hide()
    except Exception as e:
        log(f"隐藏计数器失败: {e}")

# 执行初始化
init_plugin()

log("=" * 50)
