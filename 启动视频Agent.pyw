# -*- coding: utf-8 -*-
"""Video Insight 启动器（无控制台窗口）"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from gui_tk import VideoInsightApp
VideoInsightApp().run()
