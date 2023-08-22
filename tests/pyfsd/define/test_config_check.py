from unittest import TestCase

from pyfsd.define.config_check import (
    ConfigKeyError,
    ConfigTypeError,
    ConfigValueError,
    LiteralValue,
    MayExist,
    UnionType,
    explainType,
    verifyAllConfigStruct,
    verifyConfigStruct,
)


class TestConfigCheck(TestCase):
    def test_types_explain(self) -> None:
        self.assertEqual(str(UnionType(int, str)), "int or str")
        self.assertEqual(str(MayExist({})), "{}")
        self.assertEqual(str(LiteralValue(1, 2, 3)), "literally 1 or 2 or 3")

    def test_errors_explain(self) -> None:
        self.assertEqual(str(ConfigKeyError("keyname")), "'keyname'")
        self.assertEqual(
            str(ConfigTypeError("keyname", UnionType(int, str), None)),
            "'keyname' must be int or str, not NoneType",
        )
        self.assertEqual(
            str(ConfigValueError("keyname", LiteralValue(1, 2, 3), 4)),
            "'keyname' must be literally 1 or 2 or 3, not 4",
        )

    def test_explainType(self) -> None:
        self.assertEqual(explainType(int), "literally int")
        self.assertEqual(explainType(1), "int")
        self.assertEqual(explainType({}), "{}")

    def test_verifyConfigStruct(self) -> None:
        with self.assertRaises(ConfigKeyError) as catched:
            verifyConfigStruct({}, {"keyname": int})
        self.assertEqual(catched.exception.name, "keyname")
        with self.assertRaises(ConfigTypeError) as catched2:
            verifyConfigStruct(
                {"keyname": b""}, {"keyname": MayExist(UnionType(int, str))}
            )
        self.assertTupleEqual(
            (
                catched2.exception.name,
                catched2.exception.excepted,
                catched2.exception.actually,
            ),
            ("keyname", MayExist(UnionType(int, str)), b""),
        )
        with self.assertRaises(ConfigValueError) as catched3:
            verifyConfigStruct(
                {"keyname": "string"}, {"keyname": LiteralValue("114514")}
            )
        self.assertTupleEqual(
            (
                catched3.exception.name,
                catched3.exception.excepted,
                catched3.exception.actually,
            ),
            ("keyname", LiteralValue("114514"), "string"),
        )

    def test_verifyAllConfigStruct(self) -> None:
        errors = verifyAllConfigStruct(
            {"keyname2": b"", "keyname3": "string"},
            {
                "keyname1": int,
                "keyname2": MayExist(UnionType(int, str)),
                "keyname3": LiteralValue("114514"),
            },
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.assertIsInstance(
                    error, (ConfigKeyError, ConfigTypeError, ConfigValueError)
                )
                if isinstance(error, ConfigKeyError):
                    self.assertEqual(error.name, "keyname1")
                elif isinstance(error, ConfigTypeError):
                    self.assertTupleEqual(
                        (
                            error.name,
                            error.excepted,
                            error.actually,
                        ),
                        ("keyname2", UnionType(int, str), b""),
                    )
                elif isinstance(error, ConfigValueError):
                    self.assertTupleEqual(
                        (
                            error.name,
                            error.excepted,
                            error.actually,
                        ),
                        ("keyname3", LiteralValue("114514"), "string"),
                    )
