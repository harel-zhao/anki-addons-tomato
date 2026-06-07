# Copyright: 2025
# License: GNU GPL, version 3 or later

"""
番茄钟插件 (Tomato Timer)
在 Anki 复习界面右侧显示番茄钟倒计时
左侧显示卡片复习统计

UI 设计参考 momentum_anki:深色卡片化、彩色 chip、圆润控件、明确层次。
"""

from aqt import mw, gui_hooks
from aqt.qt import *
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# 插件版本
__version__ = "1.5.0"

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

# ============================================================================
# 主题 / 配色 — 与 momentum_anki 保持视觉一致
# ============================================================================

PALETTE = {
    "bg":          "#0F172A",
    "bg_card":     "#1E293B",
    "bg_card_alt": "#0B1224",
    "text":        "#F8FAFC",
    "text_dim":    "#94A3B8",
    "text_mute":   "#64748B",
    "border":      "#334155",
    "border_strong": "#475569",
    "success":     "#10B981",
    "success_dark": "#059669",
    "warning":     "#F59E0B",
    "warning_dark": "#D97706",
    "danger":      "#EF4444",
    "danger_dark": "#DC2626",
    "accent":      "#6366F1",
    "accent_dark": "#4F46E5",
    "flame":       "#F97316",
    "tomato":      "#EF4444",
    "tomato_dark": "#B91C1C",
}

# 全局 QSS,所有 Tomato* 弹窗/Widget 共享
QSS_TOMATO = """
QWidget, QDialog {
    background: %(bg)s;
    color: %(text)s;
    font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    font-size: 13px;
}
QLabel { color: %(text)s; background: transparent; }
QLabel#Muted { color: %(text_dim)s; font-size: 11px; letter-spacing: 1px; }
QLabel#HeroLabel { color: %(text_dim)s; font-size: 11px; letter-spacing: 2px; }
QLabel#HeroNumber {
    color: %(tomato)s; font-size: 56px; font-weight: 900; letter-spacing: 4px;
}
QLabel#HeroNumberBreak {
    color: %(success)s; font-size: 56px; font-weight: 900; letter-spacing: 4px;
}
QLabel#CardTitle { font-size: 16px; font-weight: 700; color: %(text)s; }
QLabel#CardSub { color: %(text_dim)s; font-size: 11px; }

QFrame#Card {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 12px;
}
QFrame#CardAccent {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-left: 4px solid %(tomato)s;
    border-radius: 10px;
}
QFrame#CardAccentMaster {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-left: 4px solid %(success)s;
    border-radius: 10px;
}
QFrame#CardNew {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-left: 4px solid %(flame)s;
    border-radius: 10px;
}
QFrame#Divider {
    background: %(border)s;
    max-height: 1px;
    min-height: 1px;
}

QPushButton {
    background: %(accent)s;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton:hover { background: %(accent_dark)s; }
QPushButton:pressed { background: #4338CA; }
QPushButton:disabled { background: %(border_strong)s; color: %(text_dim)s; }
QPushButton#Primary { background: %(accent)s; }
QPushButton#Success { background: %(success)s; }
QPushButton#Success:hover { background: %(success_dark)s; }
QPushButton#Warning { background: %(warning)s; }
QPushButton#Warning:hover { background: %(warning_dark)s; }
QPushButton#Danger { background: %(danger)s; }
QPushButton#Danger:hover { background: %(danger_dark)s; }
QPushButton#Ghost {
    background: transparent;
    color: %(text_dim)s;
    border: 1px solid %(border)s;
}
QPushButton#Ghost:hover { background: %(bg_card)s; color: %(text)s; }
QPushButton#Reset {
    background: transparent;
    color: %(text_dim)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#Reset:hover { background: %(bg_card)s; color: %(text)s; }

QProgressBar {
    border: none;
    background: %(bg_card_alt)s;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: %(text_dim)s;
    font-size: 10px;
}
QProgressBar::chunk {
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 %(tomato)s, stop:1 %(tomato_dark)s);
}
QProgressBar#Break::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 %(success)s, stop:1 %(success_dark)s);
}

QSpinBox, QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {
    background: %(bg_card_alt)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: %(accent)s;
}
QSpinBox:focus, QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid %(accent)s;
}
QSpinBox::up-button, QSpinBox::down-button {
    background: transparent; border: none; width: 16px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: %(bg_card)s; }

QCheckBox { color: %(text)s; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1.5px solid %(border_strong)s;
    border-radius: 3px;
    background: %(bg_card_alt)s;
}
QCheckBox::indicator:checked {
    background: %(accent)s;
    border-color: %(accent)s;
    image: none;
}

QGroupBox {
    background: %(bg_card)s;
    border: 1px solid %(border)s;
    border-radius: 10px;
    margin-top: 14px;
    padding: 18px 14px 12px 14px;
    font-weight: 700;
    color: %(text)s;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: %(text)s;
}

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: %(bg_card_alt)s; width: 10px; border-radius: 5px;
}
QScrollBar::handle:vertical { background: %(border)s; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: %(border_strong)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QLabel#ModeChip {
    background: %(tomato)s22;
    color: %(tomato)s;
    padding: 4px 12px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#ModeChipBreak {
    background: %(success)s22;
    color: %(success)s;
    padding: 4px 12px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#StatChipValue {
    font-size: 20px; font-weight: 800; color: %(flame)s;
}
QLabel#StatChipLabel {
    font-size: 11px; color: %(text_dim)s; letter-spacing: 1px;
}
QLabel#Footer { color: %(text_mute)s; font-size: 10px; }
""" % PALETTE


def _apply_tomato_style(widget):
    """给一个 widget 及其子控件应用番茄钟主题"""
    widget.setStyleSheet(QSS_TOMATO)


# ============================================================================
# 配置
# ============================================================================

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
        "default_color": "#EF4444",
        "mastered_color": "#10B981",
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
# 通用:Stat Chip 组件
# ============================================================================

def _stat_chip(parent, label_text, value_text, color):
    """生成一个左侧带彩色描边的小统计卡。"""
    chip = QFrame(parent)
    chip.setStyleSheet(
        f"QFrame {{ background:{PALETTE['bg_card']};"
        f" border:1px solid {PALETTE['border']};"
        f" border-left:3px solid {color};"
        f" border-radius:8px; }}"
    )
    chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    chip.setFixedHeight(56)
    lay = QHBoxLayout(chip)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(8)
    t = QLabel(label_text)
    t.setObjectName("StatChipLabel")
    t.setStyleSheet("color:#94A3B8;font-size:10px;letter-spacing:1px;background:transparent;")
    v = QLabel(value_text)
    v.setObjectName("StatChipValue")
    v.setStyleSheet(f"color:{color};font-size:18px;font-weight:800;background:transparent;")
    lay.addWidget(t, 1)
    lay.addWidget(v)
    return chip


# ============================================================================
# 卡片复习统计Widget
# ============================================================================

class CardReviewCountWidget(QWidget):
    """卡片复习统计显示部件"""

    def __init__(self):
        super().__init__()
        self.current_card = None
        self._current_kind = "new"  # "new" | "review" | "mastered"
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        log("设置卡片统计UI...")

        # 主卡片容器
        self.card = QFrame()
        self.card.setObjectName("CardAccent")
        self.card.setStyleSheet(self._card_style("new"))

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(6)

        # 顶部 chip(显示卡片状态)
        self.kind_chip = QLabel("🆕  新卡片")
        self.kind_chip.setStyleSheet(
            "background:#F9731622;color:#F97316;padding:3px 9px;"
            "border-radius:9px;font-size:10px;font-weight:700;"
        )
        chip_row = QHBoxLayout()
        chip_row.addWidget(self.kind_chip)
        chip_row.addStretch(1)
        card_layout.addLayout(chip_row)

        # 复习次数显示(大字体)
        self.count_label = QLabel("新")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setMinimumHeight(72)
        self.count_label.setStyleSheet(
            "color:#F97316;font-size:56px;font-weight:900;"
            "letter-spacing:2px;background:transparent;"
        )
        card_layout.addWidget(self.count_label)

        # 副标题
        self.count_subtitle = QLabel("新卡片")
        self.count_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_subtitle.setObjectName("Muted")
        self.count_subtitle.setStyleSheet("color:#94A3B8;font-size:11px;letter-spacing:1px;background:transparent;")
        card_layout.addWidget(self.count_subtitle)

        # 分割线
        sep = QFrame()
        sep.setObjectName("Divider")
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#334155;")
        card_layout.addWidget(sep)

        # 正确率区
        self.rate_label = QLabel("0%")
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rate_label.setMinimumHeight(40)
        self.rate_label.setStyleSheet(
            "color:#F8FAFC;font-size:28px;font-weight:800;background:transparent;"
        )
        card_layout.addWidget(self.rate_label)

        self.rate_subtitle = QLabel("本次正确率")
        self.rate_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rate_subtitle.setObjectName("Muted")
        self.rate_subtitle.setStyleSheet("color:#94A3B8;font-size:10px;letter-spacing:1px;background:transparent;")
        card_layout.addWidget(self.rate_subtitle)

        # 总览
        self.root = QVBoxLayout()
        self.root.setContentsMargins(8, 8, 8, 8)
        self.root.addWidget(self.card)
        self.root.addStretch(1)
        self.setLayout(self.root)
        _apply_tomato_style(self)

        log("卡片统计UI设置完成")

    def _card_style(self, kind):
        """根据卡片种类返回对应的卡片样式。"""
        if kind == "mastered":
            return (
                "QFrame { background:#1E293B; border:1px solid #334155;"
                " border-left:4px solid #10B981; border-radius:10px; }"
            )
        if kind == "review":
            return (
                "QFrame { background:#1E293B; border:1px solid #334155;"
                " border-left:4px solid #EF4444; border-radius:10px; }"
            )
        # new
        return (
            "QFrame { background:#1E293B; border:1px solid #334155;"
            " border-left:4px solid #F97316; border-radius:10px; }"
        )

    def _chip_style(self, kind, text):
        """根据状态返回 chip 文本和样式。"""
        if kind == "mastered":
            return text, "background:#10B98122;color:#10B981;padding:3px 9px;border-radius:9px;font-size:10px;font-weight:700;"
        if kind == "review":
            return text, "background:#EF444422;color:#EF4444;padding:3px 9px;border-radius:9px;font-size:10px;font-weight:700;"
        return text, "background:#F9731622;color:#F97316;padding:3px 9px;border-radius:9px;font-size:10px;font-weight:700;"

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
            log(f"新卡片: {card.id}, 设置为橙色")
            self._current_kind = "new"
            self.card.setStyleSheet(self._card_style("new"))
            self.count_label.setText("新")
            self.count_label.setStyleSheet(
                "color:#F97316;font-size:56px;font-weight:900;"
                "letter-spacing:4px;background:transparent;"
            )
            self.count_subtitle.setText("新卡片 · 即将开始学习")
            chip_text, chip_style = self._chip_style("new", "🆕  新卡片")
            self.kind_chip.setText(chip_text)
            self.kind_chip.setStyleSheet(chip_style)
            # 新卡片不显示正确率
            self.count_label.show()
            self.count_subtitle.show()
            self.rate_label.hide()
            self.rate_subtitle.hide()
        else:
            # 已复习卡片显示次数和颜色
            log(f"已复习卡片: {card.id}, 复习次数: {review_count}")
            if self.should_show_green(card, review_count, card_config):
                kind = "mastered"
                color = card_config.get('mastered_color', '#10B981')
                chip_text = "🌿  已掌握"
            else:
                kind = "review"
                color = card_config.get('default_color', '#EF4444')
                chip_text = "📖  复习中"

            self._current_kind = kind
            self.card.setStyleSheet(self._card_style(kind))
            self.count_label.setText(str(review_count))
            self.count_label.setStyleSheet(
                f"color:{color};font-size:56px;font-weight:900;"
                f"letter-spacing:2px;background:transparent;"
            )
            self.count_subtitle.setText("次复习")
            ct, cs = self._chip_style(kind, chip_text)
            self.kind_chip.setText(ct)
            self.kind_chip.setStyleSheet(cs)

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
        self.kind_chip.show()

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
        self.kind_chip.show()

    def hide_all(self):
        """隐藏所有元素"""
        self.count_label.hide()
        self.count_subtitle.hide()
        self.rate_label.hide()
        self.rate_subtitle.hide()
        self.kind_chip.hide()


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

        # 整个 Widget 外面套一层 QFrame 当"卡片"
        self.outer_card = QFrame()
        self.outer_card.setObjectName("Card")
        self.outer_card.setStyleSheet(
            "QFrame { background:#1E293B; border:1px solid #334155;"
            " border-radius:14px; }"
        )
        card_layout = QVBoxLayout(self.outer_card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        # 顶部 chip 行:模式 + 状态
        top_row = QHBoxLayout()
        self.mode_chip = QLabel("🧠  专注时间")
        self.mode_chip.setObjectName("ModeChip")
        self.mode_chip.setStyleSheet(
            "background:#EF444422;color:#EF4444;padding:4px 12px;"
            "border-radius:10px;font-size:11px;font-weight:800;letter-spacing:1px;"
        )
        top_row.addWidget(self.mode_chip)
        top_row.addStretch(1)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(
            "color:#94A3B8;font-size:14px;background:transparent;"
        )
        self.status_dot.setToolTip("就绪")
        top_row.addWidget(self.status_dot)
        card_layout.addLayout(top_row)

        # 计时器大数字
        self.time_label = QLabel(f"{config['work_minutes']:02d}:00")
        self.time_label.setObjectName("HeroNumber")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setMinimumHeight(86)
        self.time_label.setStyleSheet(
            "color:#EF4444;font-size:64px;font-weight:900;letter-spacing:4px;background:transparent;"
        )
        card_layout.addWidget(self.time_label)

        # 副标题:本次阶段
        self.stage_label = QLabel("开始一次专注")
        self.stage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage_label.setObjectName("Muted")
        self.stage_label.setStyleSheet(
            "color:#94A3B8;font-size:11px;letter-spacing:2px;background:transparent;"
        )
        card_layout.addWidget(self.stage_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(self._progress_style("work"))
        card_layout.addWidget(self.progress_bar)

        # 主按钮(开始/暂停)— 大尺寸
        self.start_button = QPushButton("▶  开始专注")
        self.start_button.setObjectName("Success")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setMinimumHeight(48)
        self.start_button.setStyleSheet(
            "QPushButton { background:#10B981; color:white; border:none;"
            " padding:12px; border-radius:10px; font-size:14px; font-weight:800; }"
            "QPushButton:hover { background:#059669; }"
            "QPushButton:pressed { background:#047857; }"
            "QPushButton:disabled { background:#475569; color:#94A3B8; }"
        )
        self.start_button.clicked.connect(self.toggle_timer)
        card_layout.addWidget(self.start_button)

        # 次按钮(重置)
        self.reset_button = QPushButton("↺  重置")
        self.reset_button.setObjectName("Reset")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setMinimumHeight(40)
        self.reset_button.setStyleSheet(
            "QPushButton { background:transparent; color:#94A3B8; border:1px solid #334155;"
            " padding:8px; border-radius:8px; font-size:12px; font-weight:600; }"
            "QPushButton:hover { background:#0F172A; color:#F8FAFC; }"
        )
        self.reset_button.clicked.connect(self.reset_timer)
        card_layout.addWidget(self.reset_button)

        # 分割
        sep = QFrame()
        sep.setObjectName("Divider")
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#334155;")
        card_layout.addWidget(sep)

        # 统计 chip 行
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(8)
        self.stats_row.addWidget(self._build_count_chip())
        self.stats_row.addWidget(self._build_streak_chip())
        card_layout.addLayout(self.stats_row)

        # 底部 tip
        self.footer = QLabel("提示:开始一次专注,关闭后进度会保留。")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet("color:#475569;font-size:10px;background:transparent;")
        card_layout.addWidget(self.footer)

        # 把卡片塞进 root layout
        self.root = QVBoxLayout()
        self.root.setContentsMargins(8, 8, 8, 8)
        self.root.addWidget(self.outer_card)
        self.root.addStretch(1)
        self.setLayout(self.root)
        _apply_tomato_style(self)

        log("UI设置完成")

    def _build_count_chip(self):
        """今日番茄数 chip"""
        chip = QFrame()
        chip.setStyleSheet(
            "QFrame { background:#1E293B; border:1px solid #334155;"
            " border-left:3px solid #F97316; border-radius:8px; }"
        )
        chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        chip.setFixedHeight(56)
        lay = QVBoxLayout(chip)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(0)
        t = QLabel("今日番茄")
        t.setStyleSheet("color:#94A3B8;font-size:10px;letter-spacing:1px;background:transparent;")
        self.count_value = QLabel(f"🍅 {self.pomodoro_count}")
        self.count_value.setStyleSheet(
            "color:#F97316;font-size:16px;font-weight:800;background:transparent;"
        )
        lay.addWidget(t)
        lay.addWidget(self.count_value)
        return chip

    def _build_streak_chip(self):
        """本次模式 chip"""
        chip = QFrame()
        chip.setStyleSheet(
            "QFrame { background:#1E293B; border:1px solid #334155;"
            " border-left:3px solid #6366F1; border-radius:8px; }"
        )
        chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        chip.setFixedHeight(56)
        lay = QVBoxLayout(chip)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(0)
        t = QLabel("下次休息")
        t.setStyleSheet("color:#94A3B8;font-size:10px;letter-spacing:1px;background:transparent;")
        self.next_break = QLabel(f"☕ {config.get('break_minutes', 5)} min")
        self.next_break.setStyleSheet(
            "color:#10B981;font-size:16px;font-weight:800;background:transparent;"
        )
        lay.addWidget(t)
        lay.addWidget(self.next_break)
        return chip

    def _progress_style(self, mode):
        """进度条样式:work 用红渐变,break 用绿渐变。"""
        if mode == "break":
            return (
                "QProgressBar { border:none; background:#0B1224; border-radius:4px; height:8px; }"
                "QProgressBar::chunk { border-radius:4px;"
                " background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #10B981, stop:1 #059669); }"
            )
        return (
            "QProgressBar { border:none; background:#0B1224; border-radius:4px; height:8px; }"
            "QProgressBar::chunk { border-radius:4px;"
            " background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #EF4444, stop:1 #B91C1C); }"
        )

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
        self.status_dot.setText("●")
        self.status_dot.setStyleSheet("color:#10B981;font-size:14px;background:transparent;")
        self.status_dot.setToolTip("运行中")

    def pause_timer(self):
        """暂停计时"""
        log("暂停计时")
        self.elapsed_time = time.time() - self.start_time
        self.is_running = False
        if self.timer:
            self.timer.stop()
        self.update_button_state()
        self.status_dot.setText("●")
        self.status_dot.setStyleSheet("color:#F59E0B;font-size:14px;background:transparent;")
        self.status_dot.setToolTip("已暂停")

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
        self.status_dot.setText("●")
        self.status_dot.setStyleSheet("color:#94A3B8;font-size:14px;background:transparent;")
        self.status_dot.setToolTip("就绪")

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
            self.mode_chip.setText("🧠  专注时间")
            self.mode_chip.setStyleSheet(
                "background:#EF444422;color:#EF4444;padding:4px 12px;"
                "border-radius:10px;font-size:11px;font-weight:800;letter-spacing:1px;"
            )
            self.time_label.setObjectName("HeroNumber")
            self.time_label.setStyleSheet(
                "color:#EF4444;font-size:64px;font-weight:900;letter-spacing:4px;background:transparent;"
            )
            self.stage_label.setText("保持专注,直到时间结束")
            self.progress_bar.setStyleSheet(self._progress_style("work"))
            self.start_button.setStyleSheet(
                "QPushButton { background:#10B981; color:white; border:none;"
                " padding:12px; border-radius:10px; font-size:14px; font-weight:800; }"
                "QPushButton:hover { background:#059669; }"
                "QPushButton:pressed { background:#047857; }"
                "QPushButton:disabled { background:#475569; color:#94A3B8; }"
            )
        else:
            self.mode_chip.setText("☕  休息时间")
            self.mode_chip.setObjectName("ModeChipBreak")
            self.mode_chip.setStyleSheet(
                "background:#10B98122;color:#10B981;padding:4px 12px;"
                "border-radius:10px;font-size:11px;font-weight:800;letter-spacing:1px;"
            )
            self.time_label.setObjectName("HeroNumberBreak")
            self.time_label.setStyleSheet(
                "color:#10B981;font-size:64px;font-weight:900;letter-spacing:4px;background:transparent;"
            )
            self.stage_label.setText("放松一下,准备下一轮")
            self.progress_bar.setStyleSheet(self._progress_style("break"))
            self.start_button.setStyleSheet(
                "QPushButton { background:#6366F1; color:white; border:none;"
                " padding:12px; border-radius:10px; font-size:14px; font-weight:800; }"
                "QPushButton:hover { background:#4F46E5; }"
                "QPushButton:pressed { background:#4338CA; }"
                "QPushButton:disabled { background:#475569; color:#94A3B8; }"
            )

        # 更新统计
        today_count = get_today_pomodoro_count()
        self.count_value.setText(f"🍅 {today_count}")
        self.next_break.setText(
            f"☕ {config.get('break_minutes', 5)} min" if self.is_work_mode
            else f"🧠 {config.get('work_minutes', 25)} min"
        )

    def update_display(self):
        """更新显示"""
        total_seconds = config['work_minutes'] * 60 if self.is_work_mode else config['break_minutes'] * 60
        minutes = total_seconds // 60
        self.time_label.setText(f"{minutes:02d}:00")
        self.progress_bar.setValue(100)

    def update_button_state(self):
        """更新按钮状态"""
        if self.is_running:
            self.start_button.setText("⏸  暂停")
            self.start_button.setStyleSheet(
                "QPushButton { background:#F59E0B; color:white; border:none;"
                " padding:12px; border-radius:10px; font-size:14px; font-weight:800; }"
                "QPushButton:hover { background:#D97706; }"
                "QPushButton:pressed { background:#B45309; }"
                "QPushButton:disabled { background:#475569; color:#94A3B8; }"
            )
        else:
            self.start_button.setText("▶  开始专注" if self.is_work_mode else "▶  开始休息")
            self.update_mode_ui()  # 重置按钮配色

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
        self.setWindowTitle("⚙️  番茄钟设置")
        self.setMinimumSize(460, 360)
        self.setStyleSheet(QSS_TOMATO)
        self.setup_ui()

    def setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 标题
        title = QLabel("⚙  番茄钟设置")
        title.setStyleSheet("font-size:18px;font-weight:800;color:#F8FAFC;background:transparent;")
        sub = QLabel("为 Anki 复习配置专注与休息节奏")
        sub.setObjectName("Muted")
        sub.setStyleSheet("color:#94A3B8;font-size:11px;background:transparent;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # 番茄钟设置
        tomato_group = QGroupBox("🍅  番茄钟")
        tomato_layout = QVBoxLayout()
        tomato_layout.setSpacing(10)

        # 工作时间
        work_layout = QHBoxLayout()
        work_label = QLabel("工作时间")
        work_label.setObjectName("Muted")
        work_label.setStyleSheet("color:#94A3B8;font-size:11px;letter-spacing:1px;background:transparent;")
        self.work_spin = QSpinBox()
        self.work_spin.setRange(1, 120)
        self.work_spin.setValue(self.config.get('work_minutes', 25))
        self.work_spin.setSuffix("  分钟")
        self.work_spin.setMinimumWidth(110)
        work_layout.addWidget(work_label)
        work_layout.addStretch(1)
        work_layout.addWidget(self.work_spin)
        tomato_layout.addLayout(work_layout)

        # 休息时间
        break_layout = QHBoxLayout()
        break_label = QLabel("休息时间")
        break_label.setObjectName("Muted")
        break_label.setStyleSheet("color:#94A3B8;font-size:11px;letter-spacing:1px;background:transparent;")
        self.break_spin = QSpinBox()
        self.break_spin.setRange(1, 30)
        self.break_spin.setValue(self.config.get('break_minutes', 5))
        self.break_spin.setSuffix("  分钟")
        self.break_spin.setMinimumWidth(110)
        break_layout.addWidget(break_label)
        break_layout.addStretch(1)
        break_layout.addWidget(self.break_spin)
        tomato_layout.addLayout(break_layout)

        # 开关
        self.auto_start_check = QCheckBox("进入复习时自动开始")
        self.auto_start_check.setChecked(self.config.get('auto_start', False))
        tomato_layout.addWidget(self.auto_start_check)

        self.sound_check = QCheckBox("完成时播放提示音")
        self.sound_check.setChecked(self.config.get('sound_enabled', True))
        tomato_layout.addWidget(self.sound_check)

        tomato_group.setLayout(tomato_layout)
        layout.addWidget(tomato_group)

        # 卡片统计设置
        stats_group = QGroupBox("📊  卡片统计")
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(10)

        self.stats_enabled_check = QCheckBox("启用卡片复习统计")
        stats_enabled = self.config.get('card_review_count', {}).get('enabled', True)
        self.stats_enabled_check.setChecked(stats_enabled)
        stats_layout.addWidget(self.stats_enabled_check)

        self.show_rate_check = QCheckBox("显示正确率")
        show_rate = self.config.get('card_review_count', {}).get('show_correct_rate', True)
        self.show_rate_check.setChecked(show_rate)
        stats_layout.addWidget(self.show_rate_check)

        threshold_layout = QHBoxLayout()
        th_label = QLabel("掌握阈值")
        th_label.setObjectName("Muted")
        th_label.setStyleSheet("color:#94A3B8;font-size:11px;letter-spacing:1px;background:transparent;")
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 10)
        self.threshold_spin.setValue(self.config.get('card_review_count', {}).get('master_threshold', 3))
        self.threshold_spin.setSuffix("  次")
        self.threshold_spin.setMinimumWidth(110)
        threshold_layout.addWidget(th_label)
        threshold_layout.addStretch(1)
        threshold_layout.addWidget(self.threshold_spin)
        stats_layout.addLayout(threshold_layout)

        self.green_check = QCheckBox("已掌握时显示绿色")
        use_green = self.config.get('card_review_count', {}).get('use_green_for_mastered', True)
        self.green_check.setChecked(use_green)
        stats_layout.addWidget(self.green_check)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        layout.addStretch(1)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("Ghost")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setMinimumWidth(96)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("Success")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setMinimumHeight(40)
        save_btn.setMinimumWidth(120)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

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
                    dock_widget = QDockWidget("🍅  番茄钟", mw)
                    dock_widget.setMinimumWidth(260)
                    dock_widget.setMaximumWidth(320)
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
        tomato_menu = QMenu("🍅  显示番茄钟", mw)

        # 显示计时器开关
        tomato_display_action = QAction("☑  显示计时器", mw)
        tomato_display_action.setCheckable(True)
        tomato_display_action.setChecked(config.get('widget_enabled', True))
        tomato_display_action.triggered.connect(lambda: toggle_tomato_display())
        tomato_menu.addAction(tomato_display_action)

        # 显示卡片统计开关
        card_stats_display_action = QAction("☑  显示卡片统计", mw)
        card_stats_display_action.setCheckable(True)
        card_stats_display_action.setChecked(config.get('card_review_count', {}).get('widget_enabled', True))
        card_stats_display_action.triggered.connect(lambda: toggle_card_stats_display())
        tomato_menu.addAction(card_stats_display_action)

        # 只把子菜单挂到工具菜单;设置入口已移除(show_settings / TomatoSettingsDialog
        # 仍保留,如需再加回来只需重新 addAction 一个触发它)
        if hasattr(mw, 'form') and hasattr(mw.form, 'menuTools'):
            mw.form.menuTools.addMenu(tomato_menu)
            log("菜单已添加到工具菜单")
        else:
            mw.menuBar().addMenu(tomato_menu)
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
        review_count_dock.setMinimumWidth(160)
        review_count_dock.setMaximumWidth(180)
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

        # 卡片/笔记在浏览器或编辑器里被改时,刷新 widget,
        # 避免出现"复习时显示老数据"。
        for hook_name in (
            "card_did_update",
            "note_did_update",
            "browser_will_show",
        ):
            hook = getattr(gui_hooks, hook_name, None)
            if hook is not None:
                try:
                    hook.append(on_card_changed_outside_reviewer)
                    log(f"已注册 {hook_name} hook")
                except Exception as e:
                    log(f"注册 {hook_name} 失败: {e}")

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

def on_card_changed_outside_reviewer(*args, **kwargs):
    """浏览器/编辑器里卡片或笔记被改时,让 widget 知道下次显示要重新拉数据。

    Anki 不同版本的 hook 签名不一样(有的传 card,有的传 note,有的是 webview 等),
    所以用 *args/**kwargs 兜底,在函数内只做最轻量的"标记失效"动作,
    具体数据仍在 on_show_question 里真正查询。
    """
    try:
        # 仅仅在内存里打个标记;真要刷新要等下一次 on_show_question 触发
        global review_count_widget
        if review_count_widget is not None:
            # 清掉当前卡片引用,让下次 on_show_question 一定重新查询 revlog
            review_count_widget.current_card = None
    except Exception as e:
        log(f"卡片外修改钩子失败: {e}")

# 执行初始化
init_plugin()

log("=" * 50)
