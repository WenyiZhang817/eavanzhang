import pygame
import time
import logging
from PCA9685 import PCA9685

log_format = "%(levelname)s | %(asctime)-15s | %(message)s"
logging.basicConfig(format=log_format, level=logging.DEBUG)
import RPi.GPIO as GPIO

logger = logging.getLogger(name="GPIO")


"""
todo: 需要根据实际情况设置
"""
# 舵机参数
SERVO_CHANNEL = 1
SERVO_PWM_FREQ = 50
SERVO_START_ANGLE = 0
SERVO_FINAL_ANGLE = 18
SERVO_MINITRIM_RESOLUTION = 0.1  # 微调精度
SERVO_FINAL_RESOLUTION = 0.5  # 最后上升精度
SERVO_FINAL_STAY_DURATION = 5  # 液滴停留时长，单位秒


SHOOT_INTERVAL = 10 / 1000  # 发射脉冲宽度 10 ms
INTERVAL = 10 / 1000  # 电机脉冲间隔 10 ms
ROTATE_CYCLE_LR_UD = 100  # 位移台，移动单位距离需要的脉冲循环次数
ROTATE_CYCLE_TF = 10  # 变压器，移动单位距离需要的脉冲循环次数
UNIT = 0.1  # 坐标系单位长度
UNIT_SUFFIX = "mm"  # 坐标系长度单位

# 引脚定义：A、B、C、D
ROTATE_PINS_LR = [17, 22, 13, 12]  # 左右方向键控制
ROTATE_PINS_UD = [18, 19, 20, 21]  # 上下方向键控制
ROTATE_PINS_TF = [6, 5, 4, 23]  # 变压器控制, d、s 键控制，放大为顺时针，缩小为逆时针
REACTION_GENERATOR_PINS = [27]  # 发生器脉冲控制

"""
顺时针转动矩阵（八拍）
A - AB - B - BC - C - CD - D - DA

约定：左上为逆时针，右下为顺时针
"""
# 顺时针旋转
SEQ_CLOCKWISE = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
]

# 逆时针旋转
SEQ_ANTICLOCKWISE = [
    [1, 0, 0, 1],
    [0, 0, 0, 1],
    [0, 0, 1, 1],
    [1, 0, 1, 0],
    [0, 1, 1, 0],
    [0, 1, 0, 0],
    [1, 1, 0, 0],
    [1, 0, 0, 0],
]

SEQ_LEN = 8
WIHTE_COLOR = (255, 255, 255)
BG_COLOR = (61, 162, 113)
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 800
SCREEN_TITLE = "电机控制"


class RotateController:
    def __init__(self, width, height, title, bg_color=BG_COLOR):
        """
        初始化窗口
        """
        pygame.init()
        pygame.display.set_caption(title)
        self.screen = pygame.display.set_mode((width, height))
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.reset_screen()
        self.point_rect = pygame.draw.circle(
            self.screen, WIHTE_COLOR, (int(self.width / 2), int(self.height / 2)), 3
        )
        self.point = (0, 0)
        self.pin_init_result = {}
        self.init_pins()
        self.detect_all_pins()
        self.init_servo()

    def init_pins(self):
        """
        初始化引脚电平状态
        """
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for pin in (
            ROTATE_PINS_LR + ROTATE_PINS_UD + ROTATE_PINS_TF + REACTION_GENERATOR_PINS
        ):
            logger.info("Setup pin_%s" % pin)
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            # 初始化 pin 检测结果
            self.pin_init_result[pin] = GPIO.OUT

    def detect_all_pins(self):
        """
        检测所有 pin 口是否都在对应的模式
        """
        for pin in (
            ROTATE_PINS_LR + ROTATE_PINS_UD + ROTATE_PINS_TF + REACTION_GENERATOR_PINS
        ):
            logger.info("Detecting pin_%s" % pin)
            mode = self.get_pin_function_name(pin=pin)
            if mode != self.pin_init_result[pin]:
                logger.error("Pins detecting found error, %s init failed !!!" % pin)

        logger.info("All pins detect finished :)")

    def get_pin_function_name(self, pin):
        """
        获取引脚的模式
        """
        functions = {
            GPIO.IN: "Input",
            GPIO.OUT: "Output",
            GPIO.I2C: "I2C",
            GPIO.SPI: "SPI",
            GPIO.HARD_PWM: "HARD_PWM",
            GPIO.SERIAL: "Serial",
            GPIO.UNKNOWN: "Unknown",
        }
        logger.info("Pin_%s is %s mode" % (pin, functions[GPIO.gpio_function(pin)]))
        return GPIO.gpio_function(pin)

    def init_servo(self):
        """
        初始化舵机
        """
        logger.info("Setup Servo")
        self.servo = PCA9685(debug=True)
        self.servo.setPWMFreq(SERVO_PWM_FREQ)
        self.servo.setRotationAngle(SERVO_CHANNEL, SERVO_START_ANGLE)
        self.servo_current_angle = 0
        logger.info("Setup Servo Finish")

    def servo_rotate(
        self,
        direction,
        resolution,
        start_angle=None,
        end_angle=None,
        record_angle=False,
    ):
        """
        舵机调整
        Args:
            direction (int): 方向，取值 1 或 -1
            resolution (int or float): 精度
            start_angle (int or float, optional): 起始角度. Defaults to None.
            end_angle (int or float, optional): 结束角度. Defaults to None.
            record_angle (bool, optional): 是否记录角度. Defaults to False.
        """
        logger.debug(
            "servo_rotate[direction:%s][resolution:%s][start_angle:%s][end_angle:%s][record_angle:%s]"
            % (direction, resolution, start_angle, end_angle, record_angle)
        )
        if start_angle and end_angle:
            start = start_angle * int(1 / resolution)
            end = end_angle * int(1 / resolution)
            direction = 1 if end > start else -1
        else:
            start = self.servo_current_angle * int(1 / resolution)
            end = (self.servo_current_angle + direction * resolution) * int(
                1 / resolution
            )
        for i in range(int(start), int(end), direction):
            self.servo.setRotationAngle(SERVO_CHANNEL, i / int(1 / resolution))
            if i / int(1 / resolution) < 80:
                self.servo.setRotationAngle(0, i / int(1 / resolution))
            if record_angle:
                self.servo_current_angle = i / int(1 / resolution)
            # todo, 暂时固定这个间隔，修改这里控制微调快慢
            time.sleep(0.05)
        return

    def reset_screen(self):
        """
        重置画面
        """
        self.screen.fill(self.bg_color)
        self.draw_coordinate_system()
        self.draw_text(
            text="By Locker",
            pos=(self.width - 60, self.height - 20),
            color=WIHTE_COLOR,
            underline=True,
        )

    def draw_text(
        self,
        pos,
        text,
        color=(0, 0, 0),
        font_bold=False,
        font_size=15,
        font_italic=False,
        underline=False,
    ):
        """
        文字显示
        surface_handle：surface句柄
        pos：文字显示位置
        color:文字颜色
        font_bold:是否加粗
        font_size:字体大小
        font_italic:是否斜体
        underline: 是否下划线
        """
        cur_font = pygame.font.Font(None, font_size)
        cur_font.set_underline(underline)
        cur_font.set_bold(font_bold)
        cur_font.set_italic(font_italic)
        text_fmt = cur_font.render(text, True, color)
        self.screen.blit(text_fmt, pos)

    def draw_coordinate_system(self):
        """
        画坐标系
        """
        color = 0, 0, 0
        width = 1
        # 画坐标系 Surface, color, start_pos, end_pos, width=1
        pygame.draw.line(
            self.screen,
            color,
            (10, self.height / 2),
            (self.width - 10, self.height / 2),
            width,
        )
        pygame.draw.polygon(
            self.screen,
            color,
            [
                (self.width - 4, self.height / 2),
                (self.width - 10, self.height / 2 + 4),
                (self.width - 10, self.height / 2 - 4),
            ],
        )
        pygame.draw.line(
            self.screen,
            color,
            (self.width / 2, 10),
            (self.width / 2, self.height - 10),
            width,
        )
        pygame.draw.polygon(
            self.screen,
            color,
            [
                (self.width / 2, 4),
                (self.width / 2 + 4, 10),
                (self.width / 2 - 4, 10),
            ],
        )

        x_list_pos = []
        x_list_neg = []
        y_list_pos = []
        y_list_neg = []
        offset = 10  # 轴标间隔
        i = 0
        while (offset * i) < self.width / 2 or (offset * i) < self.height / 2:
            if (offset * i) < self.width / 2:
                x_list_pos.append(int(self.width / 2 + (offset * i)))
                x_list_neg.append(int(self.width / 2 - (offset * i)))
            if (offset * i) < self.height / 2:
                y_list_pos.append(int(self.height / 2 - (offset * i)))
                y_list_neg.append(int(self.height / 2 + (offset * i)))
            i += 1
        num = UNIT * 5
        for index in range(len(x_list_pos)):
            offset = 8 if index % 5 == 0 else 4
            x_item = x_list_pos[index]
            pygame.draw.line(
                self.screen,
                color,
                (x_item, self.height / 2 - offset),
                (x_item, self.height / 2),
                width,
            )
            if index % 5 == 0 and index > 0:
                self.draw_text(
                    text=str(num), pos=(x_item - 5, self.height / 2 + 8), font_size=20
                )
                num += UNIT * 5
        num = -UNIT * 5
        for index in range(len(x_list_neg)):
            offset = 8 if index % 5 == 0 else 4
            x_item = x_list_neg[index]
            pygame.draw.line(
                self.screen,
                color,
                (x_item, self.height / 2 - offset),
                (x_item, self.height / 2),
                width,
            )
            if index % 5 == 0 and index > 0:
                self.draw_text(
                    text=str(num), pos=(x_item - 10, self.height / 2 + 8), font_size=20
                )
                num -= UNIT * 5
        num = UNIT * 5
        for index in range(len(y_list_pos)):
            offset = 8 if index % 5 == 0 else 4
            y_item = y_list_pos[index]
            pygame.draw.line(
                self.screen,
                color,
                (self.width / 2, y_item),
                (self.width / 2 + offset, y_item),
                width,
            )
            if index % 5 == 0 and index > 0:
                self.draw_text(
                    text=str(num), pos=(self.width / 2 - 25, y_item - 2), font_size=20
                )
                num += UNIT * 5
        num = -UNIT * 5
        for index in range(len(y_list_neg)):
            offset = 8 if index % 5 == 0 else 4
            y_item = y_list_neg[index]
            pygame.draw.line(
                self.screen,
                color,
                (self.width / 2, y_item),
                (self.width / 2 + offset, y_item),
                width,
            )
            if index % 5 == 0 and index > 0:
                self.draw_text(
                    text=str(num), pos=(self.width / 2 - 27, y_item - 4), font_size=20
                )
                num -= UNIT * 5

    def move_point(self, key):
        """
        移动标记点
        """
        if key == pygame.K_LEFT:
            x, y = (-10, 0)
            self.point = (round(self.point[0] - UNIT, 1), self.point[1])
        elif key == pygame.K_RIGHT:
            x, y = (10, 0)
            self.point = (round(self.point[0] + UNIT, 1), self.point[1])
        elif key == pygame.K_UP:
            x, y = (0, -10)
            self.point = (self.point[0], round(self.point[1] + UNIT, 1))
        elif key == pygame.K_DOWN:
            x, y = (0, 10)
            self.point = (self.point[0], round(self.point[1] - UNIT, 1))
        else:
            return
        self.reset_screen()
        new_x = self.point_rect.centerx + x
        new_y = self.point_rect.centery + y
        text_x = new_x if new_x >= self.width / 2 else new_x - 30
        text_y = new_y if new_y >= self.height / 2 else new_y - 20
        self.point_rect = pygame.draw.circle(
            self.screen, WIHTE_COLOR, (new_x, new_y), 3
        )
        pygame.draw.line(
            self.screen,
            WIHTE_COLOR,
            (new_x, self.height / 2),
            (new_x, new_y),
            1,
        )
        pygame.draw.line(
            self.screen,
            WIHTE_COLOR,
            (self.width / 2, new_y),
            (new_x, new_y),
            1,
        )
        self.draw_text(
            text=f"({self.point[0]}{UNIT_SUFFIX}, {self.point[1]}{UNIT_SUFFIX})",
            pos=(text_x, text_y),
            font_size=20,
            color=WIHTE_COLOR,
        )

    def rotate(self, key):
        """
        电机旋转控制
        """
        if key in [pygame.K_LEFT, pygame.K_UP, pygame.K_d]:
            seq = SEQ_ANTICLOCKWISE
        else:
            seq = SEQ_CLOCKWISE

        if key in [pygame.K_LEFT, pygame.K_RIGHT]:
            rotate_pins = ROTATE_PINS_LR
            rotate_cycle = ROTATE_CYCLE_LR_UD
        elif key in [pygame.K_UP, pygame.K_DOWN]:
            rotate_pins = ROTATE_PINS_UD
            rotate_cycle = ROTATE_CYCLE_LR_UD
        else:
            rotate_pins = ROTATE_PINS_TF
            rotate_cycle = ROTATE_CYCLE_TF

        cycle_couter = 0
        step_couter = 0
        while cycle_couter <= rotate_cycle:
            GPIO.output(rotate_pins, tuple(seq[step_couter]))

            cycle_couter += 1
            step_couter += 1

            step_couter = 0 if step_couter >= SEQ_LEN else step_couter
            time.sleep(INTERVAL)

    def shoot_pulse(self):
        """
        脉冲发射
        """
        for pin in REACTION_GENERATOR_PINS:
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(SHOOT_INTERVAL)  # the high level will last 0.01s(10ms)
            GPIO.output(pin, GPIO.LOW)


if __name__ == "__main__":
    rotate_controller = RotateController(
        width=SCREEN_WIDTH, height=SCREEN_HEIGHT, title=SCREEN_TITLE
    )
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key in [
                    pygame.K_LEFT,
                    pygame.K_RIGHT,
                    pygame.K_UP,
                    pygame.K_DOWN,
                    pygame.K_d,
                    pygame.K_s,
                ]:  # 位移台步进电机
                    rotate_controller.rotate(event.key)
                    rotate_controller.move_point(event.key)
                elif event.key == pygame.K_v:  # 液滴发射控制
                    rotate_controller.shoot_pulse()
                elif event.key == pygame.K_n:  # 舵机微调，角度减小
                    rotate_controller.servo_rotate(
                        direction=-1,
                        resolution=SERVO_MINITRIM_RESOLUTION,
                        record_angle=True,
                    )
                elif event.key == pygame.K_m:  # 舵机微调，角度增大
                    rotate_controller.servo_rotate(
                        direction=1,
                        resolution=SERVO_MINITRIM_RESOLUTION,
                        record_angle=True,
                    )
                elif event.key == pygame.K_b:  #  液滴到达最终位置停留一段时间再回来
                    rotate_controller.servo_rotate(
                        direction=1,
                        start_angle=rotate_controller.servo_current_angle,
                        end_angle=SERVO_FINAL_ANGLE,
                        resolution=SERVO_FINAL_RESOLUTION,
                    )
                    time.sleep(SERVO_FINAL_STAY_DURATION)
                    rotate_controller.servo_rotate(
                        direction=-1,
                        start_angle=SERVO_FINAL_ANGLE,
                        end_angle=rotate_controller.servo_current_angle,
                        resolution=SERVO_FINAL_RESOLUTION,
                    )
                elif event.key == pygame.K_ESCAPE:  # 退出程序
                    pygame.quit()
                    GPIO.cleanup()
                    rotate_controller.servo.exit_PCA9685()
                    exit(0)
        pygame.display.flip()
