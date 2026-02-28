#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PDF报告生成模块
PDF Report Generation Module
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import io

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """PDF报告生成器"""

    def __init__(self, config=None):
        """
        初始化PDF报告生成器

        Args:
            config: RAG配置对象
        """
        from api_service.core.rag_config import rag_settings, get_report_path, get_template_path, get_font_path

        self.config = config or rag_settings
        self.report_path = get_report_path()
        self.template_path = get_template_path()
        self.font_path = get_font_path()

        # 初始化报告生成器
        self._init_report_generator()

    def _init_report_generator(self):
        """初始化报告生成器"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            self.canvas_module = canvas
            self.A4 = A4
            self.colors = colors

            # 尝试注册中文字体
            self._register_fonts()

            logger.info("PDF report generator initialized")

        except ImportError:
            logger.error("ReportLab not installed. Install with: pip install reportlab")
            raise

    def _register_fonts(self):
        """注册中文字体"""
        try:
            # 尝试注册常见的中文字体
            font_paths = [
                # Windows系统字体
                r"C:\Windows\Fonts\simhei.ttf",      # 黑体
                r"C:\Windows\Fonts\simkai.ttf",      # 楷体
                r"C:\Windows\Fonts\msyhbd.ttf",     # 微软雅黑
                r"C:\Windows\Fonts\simsun.ttc",     # 宋体
                # Linux系统字体
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                # macOS系统字体
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti.ttc",
            ]

            for font_path in font_paths:
                if Path(font_path).exists():
                    try:
                        from reportlab.pdfbase import pdfmetrics
                        from reportlab.pdfbase.ttfonts import TTFont

                        # 注册简体中文字体
                        pdfmetrics.registerFont(TTFont('SimHei', font_path, 'UTF-8'))
                        logger.info(f"Registered font: {font_path}")
                        self.chinese_font = 'SimHei'
                        return
                    except Exception as e:
                        continue

            # 如果没有找到中文字体，使用默认字体
            self.chinese_font = None
            logger.warning("No Chinese font found, using default font")

        except Exception as e:
            logger.error(f"Failed to register fonts: {e}")
            self.chinese_font = None

    def generate_tongue_diagnosis_report(
        self,
        diagnosis_data: Dict[str, Any],
        user_info: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None
    ) -> str:
        """
        生成舌诊诊断报告

        Args:
            diagnosis_data: 诊断数据
            user_info: 用户信息
            filename: 文件名 (可选)

        Returns:
            生成的PDF文件路径
        """
        try:
            # 创建文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"tongue_diagnosis_report_{timestamp}.pdf"

            file_path = self.report_path / filename

            # 创建PDF画布
            c = self.canvas_module.Canvas(str(file_path), pagesize=self.A4)

            # 页面尺寸
            width, height = self.A4
            margin = 50

            # 生成报告内容
            self._draw_header(c, width, height, margin, user_info)
            self._draw_tongue_analysis(c, width, height, margin, diagnosis_data)
            self._draw_syndrome_diagnosis(c, width, height, margin, diagnosis_data)
            self._draw_health_recommendations(c, width, height, margin, diagnosis_data)
            self._draw_risk_assessment(c, width, height, margin, diagnosis_data)
            self._draw_disclaimer(c, width, height, margin)

            # 保存PDF
            c.save()

            logger.info(f"PDF report generated: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise

    def _draw_header(self, c, width, height, margin, user_info):
        """绘制报告头部"""
        # 标题
        title = "AI舌诊智能诊断报告"
        subtitle = "AI Tongue Diagnosis Report"

        # 绘制装饰线
        c.setFillColor(self.colors.HexColor('#2c3e50'))
        c.rect(margin, height - margin - 80, width - 2*margin, 80, fill=1, stroke=0)

        # 绘制标题
        c.setFillColor(self.colors.white)
        if self.chinese_font:
            c.setFont(self.chinese_font, 24)
        else:
            c.setFont('Helvetica-Bold', 24)
        c.drawString(margin + 20, height - margin - 50, title)

        # 绘制副标题
        c.setFont('Helvetica', 12)
        c.drawString(margin + 20, height - margin - 70, subtitle)

        # 生成日期
        date_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        c.setFillColor(self.colors.gray)
        c.setFont('Helvetica', 10)
        c.drawString(width - margin - 150, height - margin - 30, f"报告日期: {date_str}")

        # 用户信息
        if user_info:
            y_pos = height - margin - 100
            c.setFillColor(self.colors.black)
            c.setFont('Helvetica', 11)

            user_lines = [
                f"姓名: {user_info.get('name', '未知')}",
                f"性别: {user_info.get('gender', '未知')}",
                f"年龄: {user_info.get('age', '未知')}",
                f"联系方式: {user_info.get('contact', '未知')}"
            ]

            for i, line in enumerate(user_lines):
                c.drawString(margin, y_pos - i * 20, line)

            return y_pos - len(user_lines) * 20 - 20

        return height - margin - 120

    def _draw_tongue_analysis(self, c, width, height, margin, diagnosis_data):
        """绘制舌象分析部分"""
        y_pos = height - margin - 180

        # 标题
        c.setFillColor(self.colors.HexColor('#3498db'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 16)
        else:
            c.setFont('Helvetica-Bold', 16)
        c.drawString(margin, y_pos, "一、舌象特征分析")

        y_pos -= 30

        # 舌象分析数据
        tongue_analysis = diagnosis_data.get('tongue_analysis', {})

        # 舌色分析
        self._draw_analysis_section(c, margin, y_pos, "舌色分析", tongue_analysis.get('tongue_color', {}))
        y_pos -= 80

        # 苔色分析
        self._draw_analysis_section(c, margin, y_pos, "苔色分析", tongue_analysis.get('coating_analysis', {}))
        y_pos -= 80

        # 舌形分析
        self._draw_analysis_section(c, margin, y_pos, "舌形分析", tongue_analysis.get('tongue_shape_analysis', {}))
        y_pos -= 80

        # 特殊特征分析
        special_features = tongue_analysis.get('special_features_analysis', {})
        if special_features.get('observations'):
            self._draw_analysis_section(c, margin, y_pos, "特殊特征分析", special_features)
            y_pos -= 80

        return y_pos

    def _draw_analysis_section(self, c, margin, y_pos, title, analysis_data):
        """绘制分析部分"""
        # 子标题
        c.setFillColor(self.colors.HexColor('#2c3e50'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 12)
        else:
            c.setFont('Helvetica-Bold', 12)
        c.drawString(margin + 10, y_pos, f"• {title}")

        y_pos -= 20

        # 分析内容
        c.setFillColor(self.colors.black)
        c.setFont('Helvetica', 10)

        lines = [
            f"观察结果: {analysis_data.get('observation', '无')}",
            f"中医解释: {analysis_data.get('tcm_interpretation', '无')}",
            f"临床意义: {analysis_data.get('clinical_significance', '无')}"
        ]

        for line in lines:
            words = self._wrap_text(c, line, width - 2*margin - 20)
            for word in words:
                c.drawString(margin + 20, y_pos, word)
                y_pos -= 14

    def _draw_syndrome_diagnosis(self, c, width, height, margin, diagnosis_data):
        """绘制证型诊断部分"""
        y_pos = c._y if hasattr(c, '_y') else height - margin - 180

        # 检查是否需要换页
        if y_pos < 200:
            c.showPage()
            y_pos = height - margin

        # 标题
        c.setFillColor(self.colors.HexColor('#3498db'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 16)
        else:
            c.setFont('Helvetica-Bold', 16)
        c.drawString(margin, y_pos, "二、证型诊断")

        y_pos -= 30

        # 证型数据
        syndrome_data = diagnosis_data.get('syndrome_diagnosis', {})

        # 主要证型
        c.setFillColor(self.colors.HexColor('#e74c3c'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 14)
        else:
            c.setFont('Helvetica-Bold', 14)
        primary_syndrome = syndrome_data.get('primary_syndrome', '未知')
        confidence = syndrome_data.get('confidence', 0.0)
        c.drawString(margin, y_pos, f"主要证型: {primary_syndrome} (置信度: {confidence:.2%})")

        y_pos -= 25

        # 次要证型
        secondary_syndromes = syndrome_data.get('secondary_syndromes', [])
        if secondary_syndromes:
            c.setFillColor(self.colors.black)
            c.setFont('Helvetica', 11)
            c.drawString(margin, y_pos, f"次要证型: {', '.join(secondary_syndromes)}")
            y_pos -= 25

        # 诊断依据
        c.setFillColor(self.colors.black)
        c.setFont('Helvetica', 10)
        c.drawString(margin, y_pos, "诊断依据:")
        y_pos -= 15

        diagnosis_basis = syndrome_data.get('diagnosis_basis', '无')
        words = self._wrap_text(c, diagnosis_basis, width - 2*margin - 20)
        for word in words:
            c.drawString(margin + 20, y_pos, word)
            y_pos -= 14

        y_pos -= 15

        # 中医理论解释
        c.drawString(margin, y_pos, "中医理论解释:")
        y_pos -= 15

        tcm_theory = syndrome_data.get('tcm_theory_explanation', '无')
        words = self._wrap_text(c, tcm_theory, width - 2*margin - 20)
        for word in words:
            c.drawString(margin + 20, y_pos, word)
            y_pos -= 14

        c._y = y_pos
        return y_pos

    def _draw_health_recommendations(self, c, width, height, margin, diagnosis_data):
        """绘制健康建议部分"""
        y_pos = c._y if hasattr(c, '_y') else height - margin - 180

        # 检查是否需要换页
        if y_pos < 200:
            c.showPage()
            y_pos = height - margin

        # 标题
        c.setFillColor(self.colors.HexColor('#3498db'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 16)
        else:
            c.setFont('Helvetica-Bold', 16)
        c.drawString(margin, y_pos, "三、健康调理建议")

        y_pos -= 30

        # 健康建议数据
        health_data = diagnosis_data.get('health_recommendations', {})

        # 饮食指导
        self._draw_guidance_section(c, margin, y_pos, "饮食调理", health_data.get('dietary_guidance', {}))
        y_pos -= 100

        # 生活指导
        self._draw_guidance_section(c, margin, y_pos, "生活方式", health_data.get('lifestyle_guidance', {}))
        y_pos -= 100

        # 情绪指导
        self._draw_guidance_section(c, margin, y_pos, "情绪调节", health_data.get('emotional_guidance', {}))
        y_pos -= 100

        c._y = y_pos
        return y_pos

    def _draw_guidance_section(self, c, margin, y_pos, title, guidance_data):
        """绘制指导部分"""
        # 子标题
        c.setFillColor(self.colors.HexColor('#27ae60'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 14)
        else:
            c.setFont('Helvetica-Bold', 14)
        c.drawString(margin, y_pos, title)

        y_pos -= 20

        c.setFillColor(self.colors.black)
        c.setFont('Helvetica', 10)

        # 调理原则
        principle = guidance_data.get('principle', '无')
        c.drawString(margin, y_pos, f"调理原则: {principle}")
        y_pos -= 15

        # 推荐项目
        recommended = guidance_data.get('recommended_foods', []) if title == "饮食调理" else []
        if recommended:
            c.drawString(margin, y_pos, "推荐项目:")
            y_pos -= 10
            for item in recommended:
                c.drawString(margin + 20, y_pos, f"• {item}")
                y_pos -= 14
            y_pos -= 5

        # 禁忌项目
        avoid = guidance_data.get('avoid_foods', []) if title == "饮食调理" else []
        if avoid:
            c.drawString(margin, y_pos, "禁忌项目:")
            y_pos -= 10
            for item in avoid:
                c.drawString(margin + 20, y_pos, f"• {item}")
                y_pos -= 14
            y_pos -= 5

        # 运动建议
        exercise = guidance_data.get('exercise', [])
        if exercise and title == "生活方式":
            c.drawString(margin, y_pos, "运动建议:")
            y_pos -= 10
            for item in exercise:
                c.drawString(margin + 20, y_pos, f"• {item}")
                y_pos -= 14
            y_pos -= 5

        # 其他详细建议
        for key in ['sleep', 'daily_routine', 'environment', 'mood_regulation', 'stress_management', 'mindfulness']:
            value = guidance_data.get(key)
            if value:
                c.drawString(margin, y_pos, f"{key}: {value}")
                y_pos -= 14

    def _draw_risk_assessment(self, c, width, height, margin, diagnosis_data):
        """绘制风险评估部分"""
        y_pos = c._y if hasattr(c, '_y') else height - margin - 180

        # 检查是否需要换页
        if y_pos < 200:
            c.showPage()
            y_pos = height - margin

        # 标题
        c.setFillColor(self.colors.HexColor('#3498db'))
        if self.chinese_font:
            c.setFont(self.chinese_font, 16)
        else:
            c.setFont('Helvetica-Bold', 16)
        c.drawString(margin, y_pos, "四、健康风险评估")

        y_pos -= 30

        # 风险评估数据
        risk_data = diagnosis_data.get('risk_assessment', {})

        c.setFillColor(self.colors.black)
        c.setFont('Helvetica', 10)

        # 当前健康状态
        status = risk_data.get('current_health_status', '无评估')
        c.drawString(margin, y_pos, f"当前健康状态: {status}")
        y_pos -= 20

        # 潜在风险
        risks = risk_data.get('potential_risks', [])
        if risks:
            c.drawString(margin, y_pos, "潜在风险因素:")
            y_pos -= 10
            for risk in risks:
                c.drawString(margin + 20, y_pos, f"• {risk}")
                y_pos -= 14
            y_pos -= 5

        # 建议
        recommendations = risk_data.get('recommendations', [])
        if recommendations:
            c.drawString(margin, y_pos, "改善建议:")
            y_pos -= 10
            for rec in recommendations:
                c.drawString(margin + 20, y_pos, f"• {rec}")
                y_pos -= 14

        c._y = y_pos
        return y_pos

    def _draw_disclaimer(self, c, width, height, margin):
        """绘制免责声明"""
        y_pos = c._y if hasattr(c, '_y') else height - margin - 180

        # 检查是否需要换页
        if y_pos < 150:
            c.showPage()
            y_pos = height - margin

        # 绘制分隔线
        c.setLineWidth(1)
        c.setStrokeColor(self.colors.gray)
        c.line(margin, y_pos, width - margin, y_pos)
        y_pos -= 20

        # 免责声明
        disclaimer = diagnosis_data.get('medical_disclaimer', '')

        c.setFillColor(self.colors.gray)
        c.setFont('Helvetica', 8)

        words = self._wrap_text(c, disclaimer, width - 2*margin - 20)
        for word in words:
            c.drawString(margin, y_pos, word)
            y_pos -= 12

        # 版权信息
        copyright = f"© {datetime.now().year} AI舌诊智能诊断系统 - 版权所有"
        c.setFillColor(self.colors.lightgray)
        c.drawString(margin, y_pos - 20, copyright)

    def _wrap_text(self, c, text, max_width):
        """文本换行"""
        from reportlab.pdfbase.pdfmetrics import stringWidth

        words = []
        current_line = ""

        for char in text:
            test_line = current_line + char
            width = stringWidth(test_line, c._fontname, c._fontsize)

            if width > max_width:
                if current_line:
                    words.append(current_line)
                current_line = char
            else:
                current_line = test_line

        if current_line:
            words.append(current_line)

        return words


# 全局PDF报告生成器实例
_pdf_generator = None


def get_pdf_generator():
    """获取PDF报告生成器实例"""
    global _pdf_generator
    if _pdf_generator is None:
        _pdf_generator = PDFReportGenerator()
    return _pdf_generator