"""
Author: lockerzhang
Date: 2021-10-23 10:47:34
LastEditors: lockerzhang
LastEditTime: 2021-10-23 10:47:34
FilePath: /locker/pulse.py
Description:: Say something
"""
# Software pulse.py
# coding=utf-8

import RPi.GPIO as GPIO
import time
import pygame

pygame.init()
P_pulse = 27  # GPIO0端口号，根据实际修改
# fPWM = 1  # Hz (软件PWM方式，频率不能设置过高)
# servo LD-20MG: pulse width is form 0.5ms to 2.5ms
# period is 20ms, duty is form 2.5% to 12.5%


def setup():
    global pulse1
    GPIO.setmode(GPIO.BCM)  # setup the BCM coding pin
    GPIO.setup(P_pulse, GPIO.OUT)
    # pulse1 = GPIO.PWM(P_pulse, fPWM)
    # pulse1.start(0)


def shootPulse():
    # direction = angle*(a-b)/180
    # duty = b+direction
    # duty =
    # pwm1.ChangeDutyCycle(duty)
    # print "angle =", angle, "-> duty =", duty
    # time.sleep(0.5)
    GPIO.output(P_pulse, GPIO.HIGH)
    time.sleep(0.01)  # the high level will last 0.01s(10ms)
    GPIO.output(P_pulse, GPIO.LOW)
    time.sleep(1)


setup()
screen = pygame.display.set_mode((800, 600))
while True:
    # print('1')
    for event in pygame.event.get():
        # print('2')
        if event.type == pygame.QUIT:
            pygame.quit()
            exit(0)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_v:
                shootPulse()
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                exit(0)
