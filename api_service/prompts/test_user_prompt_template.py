# -*- coding: utf-8 -*-
"""
Unit tests for User Prompt Template Module

Test cases for:
- Field mapping correctness
- Dynamic prompt generation
- Template selection logic
- User info section building
- Special features formatting
"""

import unittest
import sys
from pathlib import Path
import io
import contextlib

# Set UTF-8 encoding for stdout
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api_service.prompts.user_prompt_template import (
    UserPromptBuilder,
    ClassificationResult,
    UserInfo,
    FieldMapping,
    PromptTemplates,
    create_user_prompt,
    TongueColor,
    CoatingColor,
    TongueShape,
    CoatingQuality,
)


class TestFieldMapping(unittest.TestCase):
    """Test field mapping configurations"""

    def test_tongue_color_mapping(self):
        """Test tongue color index to name mapping"""
        mapping = FieldMapping.TONGUE_COLOR_MAPPING

        # Test all indices
        self.assertEqual(mapping[0][0], "淡红舌")
        self.assertEqual(mapping[1][0], "红舌")
        self.assertEqual(mapping[2][0], "绛紫舌")
        self.assertEqual(mapping[3][0], "淡白舌")

    def test_coating_color_mapping(self):
        """Test coating color index to name mapping"""
        mapping = FieldMapping.COATING_COLOR_MAPPING

        self.assertEqual(mapping[0][0], "白苔")
        self.assertEqual(mapping[1][0], "黄苔")
        self.assertEqual(mapping[2][0], "黑苔")
        self.assertEqual(mapping[3][0], "花剥苔")

    def test_tongue_shape_mapping(self):
        """Test tongue shape index to name mapping"""
        mapping = FieldMapping.TONGUE_SHAPE_MAPPING

        self.assertEqual(mapping[0][0], "正常")
        self.assertEqual(mapping[1][0], "胖大舌")
        self.assertEqual(mapping[2][0], "瘦薄舌")

    def test_coating_quality_mapping(self):
        """Test coating quality index to name mapping"""
        mapping = FieldMapping.COATING_QUALITY_MAPPING

        self.assertEqual(mapping[0][0], "薄苔")
        self.assertEqual(mapping[1][0], "厚苔")
        self.assertEqual(mapping[2][0], "腐苔")
        self.assertEqual(mapping[3][0], "腻苔")

    def test_feature_name_mapping(self):
        """Test special feature name mapping"""
        mapping = FieldMapping.FEATURE_NAME_MAPPING

        self.assertEqual(mapping["red_dots"], "红点")
        self.assertEqual(mapping["cracks"], "裂纹")
        self.assertEqual(mapping["teeth_marks"], "齿痕")


class TestClassificationResult(unittest.TestCase):
    """Test ClassificationResult dataclass"""

    def test_to_dict_method(self):
        """Test ClassificationResult.to_dict() method"""
        result = ClassificationResult(
            tongue_color={"prediction": "淡红舌", "confidence": 0.9, "description": "test"},
            coating_color={"prediction": "白苔", "confidence": 0.8, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.85, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.75, "description": "test"},
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "健康舌", "confidence": 0.9, "description": "test"},
        )

        result_dict = result.to_dict()

        # Check all fields are present
        self.assertIn("tongue_color", result_dict)
        self.assertIn("coating_color", result_dict)
        self.assertIn("tongue_shape", result_dict)
        self.assertIn("coating_quality", result_dict)
        self.assertIn("special_features", result_dict)
        self.assertIn("health_status", result_dict)


class TestUserInfo(unittest.TestCase):
    """Test UserInfo dataclass"""

    def test_default_values(self):
        """Test UserInfo default values"""
        info = UserInfo()

        self.assertIsNone(info.age)
        self.assertIsNone(info.gender)
        self.assertEqual(info.symptoms, [])
        self.assertEqual(info.medical_history, [])
        self.assertIsNone(info.chief_complaint)

    def test_with_values(self):
        """Test UserInfo with values"""
        info = UserInfo(
            age=45,
            gender="男",
            symptoms=["疲劳", "失眠"],
            medical_history=["高血压"],
            chief_complaint="近期疲劳",
        )

        self.assertEqual(info.age, 45)
        self.assertEqual(info.gender, "男")
        self.assertEqual(len(info.symptoms), 2)
        self.assertEqual(len(info.medical_history), 1)
        self.assertEqual(info.chief_complaint, "近期疲劳")


class TestUserPromptBuilder(unittest.TestCase):
    """Test UserPromptBuilder class"""

    def setUp(self):
        """Set up test fixtures"""
        self.builder = UserPromptBuilder()

        # Create sample classification result
        self.sample_result = ClassificationResult(
            tongue_color={
                "prediction": "淡红舌",
                "confidence": 0.92,
                "description": "舌色淡红，气血调和",
            },
            coating_color={
                "prediction": "白苔",
                "confidence": 0.88,
                "description": "苔色薄白",
            },
            tongue_shape={
                "prediction": "正常",
                "confidence": 0.90,
                "description": "舌形适中",
            },
            coating_quality={
                "prediction": "薄苔",
                "confidence": 0.85,
                "description": "苔质薄白",
            },
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "无明显红点"},
                "cracks": {"present": False, "confidence": 0.0, "description": "无明显裂纹"},
                "teeth_marks": {
                    "present": False,
                    "confidence": 0.0,
                    "description": "无明显齿痕",
                },
            },
            health_status={
                "prediction": "健康舌",
                "confidence": 0.91,
                "description": "舌象正常",
            },
        )

        self.sample_user_info = UserInfo(
            age=35, gender="女", symptoms=["乏力"], chief_complaint="感觉疲劳"
        )

    def test_base_template_generation(self):
        """Test base template prompt generation"""
        prompt = self.builder.build_prompt(self.sample_result)

        # Check that prompt is generated
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

        # Check for key content (using Unicode escapes for Windows compatibility)
        self.assertIn("淡红舌", prompt)
        self.assertIn("白苔", prompt)
        self.assertIn("正常", prompt)
        self.assertIn("薄苔", prompt)
        self.assertIn("健康舌", prompt)
        self.assertIn("92.00%", prompt)

    def test_healthy_template_selection(self):
        """Test that healthy template is selected for healthy tongue"""
        # High confidence healthy tongue
        result = ClassificationResult(
            tongue_color={
                "prediction": "淡红舌",
                "confidence": 0.9,
                "description": "test",
            },
            coating_color={"prediction": "白苔", "confidence": 0.9, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.9, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.9, "description": "test"},
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "健康舌", "confidence": 0.91, "description": "test"},
        )

        prompt = self.builder.build_prompt(result)

        # Check healthy template indicators
        self.assertIn("健康舌象", prompt)
        self.assertIn("健康维持建议", prompt)

    def test_simplified_template_for_low_confidence(self):
        """Test that simplified template is used for low confidence"""
        # Create result with low confidence feature
        result = ClassificationResult(
            tongue_color={"prediction": "淡红舌", "confidence": 0.4, "description": "test"},
            coating_color={"prediction": "白苔", "confidence": 0.9, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.9, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.9, "description": "test"},
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "不健康舌", "confidence": 0.9, "description": "test"},
        )

        prompt = self.builder.build_prompt(result)

        # Check simplified template indicators
        self.assertIn("特征提取不确定", prompt)
        self.assertIn("谨慎分析", prompt)

    def test_user_info_section(self):
        """Test user info section building"""
        prompt = self.builder.build_prompt(self.sample_result, self.sample_user_info)

        # Check user info is included
        self.assertIn("年龄: 35岁", prompt)
        self.assertIn("性别: 女", prompt)
        self.assertIn("症状: 乏力", prompt)
        self.assertIn("主诉: 感觉疲劳", prompt)

    def test_special_features_with_present_features(self):
        """Test special features section when features are present"""
        result = ClassificationResult(
            tongue_color={"prediction": "红舌", "confidence": 0.9, "description": "test"},
            coating_color={"prediction": "黄苔", "confidence": 0.9, "description": "test"},
            tongue_shape={"prediction": "胖大舌", "confidence": 0.9, "description": "test"},
            coating_quality={"prediction": "厚苔", "confidence": 0.9, "description": "test"},
            special_features={
                "red_dots": {"present": True, "confidence": 0.8, "description": "热毒蕴结"},
                "cracks": {"present": True, "confidence": 0.7, "description": "阴血不足"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "不健康舌", "confidence": 0.9, "description": "test"},
        )

        prompt = self.builder.build_prompt(result)

        # Check special features are formatted correctly
        self.assertIn("红点: 存在", prompt)
        self.assertIn("裂纹: 存在", prompt)
        self.assertIn("齿痕: 无明显表现", prompt)
        self.assertIn("80.00%", prompt)
        self.assertIn("70.00%", prompt)

    def test_no_user_info(self):
        """Test prompt generation without user info"""
        prompt = self.builder.build_prompt(self.sample_result, user_info=None)

        # Should contain placeholder message
        self.assertIn("未提供用户信息", prompt)

    def test_confidence_formatting(self):
        """Test confidence value formatting as percentage"""
        prompt = self.builder.build_prompt(self.sample_result)

        # Check confidence is formatted as percentage
        self.assertIn("92.00%", prompt)
        self.assertIn("88.00%", prompt)
        self.assertIn("90.00%", prompt)
        self.assertIn("85.00%", prompt)
        self.assertIn("91.00%", prompt)


class TestCreateUserPrompt(unittest.TestCase):
    """Test create_user_prompt convenience function"""

    def test_dict_input(self):
        """Test with dictionary input instead of objects"""
        model_output = {
            "tongue_color": {"prediction": "淡红舌", "confidence": 0.9, "description": "test"},
            "coating_color": {"prediction": "白苔", "confidence": 0.85, "description": "test"},
            "tongue_shape": {"prediction": "正常", "confidence": 0.88, "description": "test"},
            "coating_quality": {"prediction": "薄苔", "confidence": 0.82, "description": "test"},
            "special_features": {
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            "health_status": {"prediction": "健康舌", "confidence": 0.9, "description": "test"},
        }

        prompt = create_user_prompt(model_output)

        self.assertIn("淡红舌", prompt)
        self.assertIn("白苔", prompt)
        self.assertIn("正常", prompt)

    def test_with_user_info_dict(self):
        """Test with user info as dictionary"""
        model_output = {
            "tongue_color": {"prediction": "淡红舌", "confidence": 0.9, "description": "test"},
            "coating_color": {"prediction": "白苔", "confidence": 0.85, "description": "test"},
            "tongue_shape": {"prediction": "正常", "confidence": 0.88, "description": "test"},
            "coating_quality": {"prediction": "薄苔", "confidence": 0.82, "description": "test"},
            "special_features": {
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            "health_status": {"prediction": "健康舌", "confidence": 0.9, "description": "test"},
        }

        user_info = {
            "age": 50,
            "gender": "男",
            "symptoms": ["失眠"],
            "medical_history": [],
            "chief_complaint": "睡眠质量差",
        }

        prompt = create_user_prompt(model_output, user_info=user_info)

        self.assertIn("年龄: 50岁", prompt)
        self.assertIn("性别: 男", prompt)
        self.assertIn("症状: 失眠", prompt)
        self.assertIn("主诉: 睡眠质量差", prompt)

    def test_template_type_selection(self):
        """Test template_type parameter"""
        model_output = {
            "tongue_color": {"prediction": "淡红舌", "confidence": 0.9, "description": "test"},
            "coating_color": {"prediction": "白苔", "confidence": 0.85, "description": "test"},
            "tongue_shape": {"prediction": "正常", "confidence": 0.88, "description": "test"},
            "coating_quality": {"prediction": "薄苔", "confidence": 0.82, "description": "test"},
            "special_features": {
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            "health_status": {"prediction": "健康舌", "confidence": 0.9, "description": "test"},
        }

        # Test with simplified template
        prompt = create_user_prompt(model_output, template_type="simplified")
        self.assertIn("特征提取不确定", prompt)


class TestPromptTemplates(unittest.TestCase):
    """Test PromptTemplates class"""

    def test_base_template_exists(self):
        """Test that base template exists and has required variables"""
        template = PromptTemplates.BASE_TEMPLATE

        # Check for required variables
        self.assertIn("{tongue_color_prediction}", template)
        # Template includes format specifiers like :.2%
        self.assertIn("{tongue_color_confidence:", template)
        self.assertIn("{coating_color_prediction}", template)
        self.assertIn("{special_features_section}", template)
        self.assertIn("{user_info_section}", template)

    def test_healthy_template_exists(self):
        """Test that healthy template exists"""
        template = PromptTemplates.HEALTHY_TEMPLATE

        self.assertIn("{tongue_color_prediction}", template)
        self.assertIn("健康维持建议", template)

    def test_simplified_template_exists(self):
        """Test that simplified template exists"""
        template = PromptTemplates.SIMPLIFIED_TEMPLATE

        self.assertIn("{tongue_color_prediction}", template)
        self.assertIn("特征提取不确定", template)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_missing_description_uses_default(self):
        """Test that missing description uses default"""
        # Use unhealthy tongue to avoid healthy template
        result = ClassificationResult(
            tongue_color={"prediction": "淡红舌", "confidence": 0.9, "description": ""},
            coating_color={"prediction": "白苔", "confidence": 0.85, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.88, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.82, "description": "test"},
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "不健康舌", "confidence": 0.9, "description": "test"},
        )

        builder = UserPromptBuilder()
        prompt = builder.build_prompt(result)

        # Should contain default description for 淡红舌
        self.assertIn("气血调和", prompt)

    def test_empty_special_features(self):
        """Test with empty special features"""
        result = ClassificationResult(
            tongue_color={"prediction": "淡红舌", "confidence": 0.9, "description": "test"},
            coating_color={"prediction": "白苔", "confidence": 0.85, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.88, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.82, "description": "test"},
            special_features={},  # Empty special features
            health_status={"prediction": "不健康舌", "confidence": 0.9, "description": "test"},
        )

        builder = UserPromptBuilder()
        # Should not raise error
        prompt = builder.build_prompt(result)
        self.assertIn("特殊特征", prompt)

    def test_unknown_prediction(self):
        """Test with unknown prediction value"""
        result = ClassificationResult(
            tongue_color={"prediction": "未知舌色", "confidence": 0.5, "description": "test"},
            coating_color={"prediction": "白苔", "confidence": 0.85, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.88, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.82, "description": "test"},
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "健康舌", "confidence": 0.9, "description": "test"},
        )

        builder = UserPromptBuilder()
        # Should not raise error
        prompt = builder.build_prompt(result)
        self.assertIn("未知舌色", prompt)

    def test_zero_confidence(self):
        """Test with zero confidence values"""
        result = ClassificationResult(
            tongue_color={"prediction": "淡红舌", "confidence": 0.0, "description": "test"},
            coating_color={"prediction": "白苔", "confidence": 0.0, "description": "test"},
            tongue_shape={"prediction": "正常", "confidence": 0.0, "description": "test"},
            coating_quality={"prediction": "薄苔", "confidence": 0.0, "description": "test"},
            special_features={
                "red_dots": {"present": False, "confidence": 0.0, "description": "test"},
                "cracks": {"present": False, "confidence": 0.0, "description": "test"},
                "teeth_marks": {"present": False, "confidence": 0.0, "description": "test"},
            },
            health_status={"prediction": "健康舌", "confidence": 0.0, "description": "test"},
        )

        builder = UserPromptBuilder()
        # Should not raise error even with all zeros
        prompt = builder.build_prompt(result)
        self.assertIn("0.00%", prompt)


def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFieldMapping))
    suite.addTests(loader.loadTestsFromTestCase(TestClassificationResult))
    suite.addTests(loader.loadTestsFromTestCase(TestUserInfo))
    suite.addTests(loader.loadTestsFromTestCase(TestUserPromptBuilder))
    suite.addTests(loader.loadTestsFromTestCase(TestCreateUserPrompt))
    suite.addTests(loader.loadTestsFromTestCase(TestPromptTemplates))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


if __name__ == "__main__":
    result = run_tests()

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
