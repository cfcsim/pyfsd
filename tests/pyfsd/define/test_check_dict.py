"""This module tests pyfsd.define.check_dict."""
from sys import version_info
from typing import Dict, List, Literal, Tuple, Union
from unittest import TestCase

if version_info < (3, 11):
    from typing import TypedDict

    from typing_extensions import NotRequired
    from typing_extensions import TypedDict as new_TypedDict

    available_typeddict = (TypedDict, new_TypedDict)
else:
    from typing import NotRequired, TypedDict  # type: ignore[no-redef,attr-defined]

    available_typeddict = (TypedDict,)  # type: ignore[assignment]


from pyfsd.define.check_dict import (
    VerifyKeyError,
    VerifyTypeError,
    assert_dict,
    assert_simple_type,
    check_dict,
    check_simple_type,
    explain_type,
    lookup_required,
)


class TestCheckDict(TestCase):
    """Test if pyfsd.define.check_dict works."""

    complex_type = Union[int, Literal["1234", 5678], List[str], Dict[int, str]]

    def test_explain_type(self) -> None:
        """Tests if explain_type works."""
        self.assertEqual(
            explain_type(self.complex_type),
            "int or '1234' or 5678 or List[str] or Dict[int, str]",
        )

    def test_explain_error(self) -> None:
        """Tests if verify errors can correctly introduce themselves."""
        self.assertEqual(
            str(VerifyTypeError("abcd", self.complex_type, b"")),
            "'abcd' must be int or '1234' or 5678 or List[str] or Dict[int, str], "
            "not bytes",
        )
        for key_error in ("missing", "leftover"):
            with self.subTest(type_=key_error):
                self.assertEqual(
                    str(VerifyKeyError("abcd", "efgh", key_error)),  # type: ignore[arg-type]
                    f"abcd['efgh'] {key_error}",
                )

    def test_check_simple_type(self) -> None:
        """Tests if check_simple_type works."""

        def generate_simple_case(correctv, typ, wrongv):  # type: ignore[no-untyped-def]
            return (correctv, typ, wrongv, (VerifyTypeError("obj", typ, wrongv),))

        # (correct_value, type, wrong_value, expected_exceptions)
        cases = (
            generate_simple_case(1, Union[int, bytes], "1"),
            generate_simple_case(b"1", Union[int, bytes], "1"),
            generate_simple_case("1234", Literal["1234", 5678], "5678"),
            (
                ["123", "456"],
                List[str],
                [123, 456],
                (
                    VerifyTypeError("obj[0]", str, 123),
                    VerifyTypeError("obj[1]", str, 456),
                ),
            ),
            (
                {1: "1", 2: "2"},
                Dict[int, str],
                {"1": 1, "2": 2},
                (
                    VerifyTypeError("obj['1']", int, "1"),
                    VerifyTypeError("obj['1']", str, 1),
                    VerifyTypeError("obj['2']", int, "2"),
                    VerifyTypeError("obj['2']", str, 2),
                ),
            ),
        )
        for correctv, typ, wrongv, exp_exc in cases:
            with self.subTest(typ=typ):
                # Check correct value
                with self.assertRaises(StopIteration):
                    next(iter(check_simple_type(correctv, typ, "obj")))
                assert_simple_type(correctv, typ, "obj")
                # Check wrong value
                self.assertEqual(tuple(check_simple_type(wrongv, typ, "obj")), exp_exc)
                with self.assertRaises(VerifyTypeError) as cm:
                    assert_simple_type(wrongv, typ, "obj")
                self.assertEqual(cm.exception, exp_exc[0])

    def test_lookup_required(self) -> None:
        """Tests if lookup_required works."""
        some_optional_dict = {"a": int, "b": NotRequired[str]}  # pyright: ignore
        self.assertEqual(tuple(lookup_required(some_optional_dict)), ("a",))
        for typed_dict in available_typeddict:
            with self.subTest(typeddict_source=typed_dict.__module__):

                class SomeOptionalDict(typed_dict):  # type: ignore[misc, valid-type]
                    a: int
                    b: NotRequired[str]  # type: ignore[valid-type]

                self.assertEqual(tuple(lookup_required(SomeOptionalDict)), ("a",))

                class AllOptionalDict(  # pyright: ignore
                    typed_dict,  # type: ignore[misc, valid-type]
                    total=False,  # type: ignore[call-arg]
                ):
                    a: int
                    b: str

                self.assertFalse(tuple(lookup_required(AllOptionalDict)))

    def test_check_dict(self) -> None:
        """Tests if check_dict works."""
        #                        (  expected_errors  )  (all)ow_unexpected_keys
        cases: Tuple[Tuple[dict, Tuple[Exception, ...], bool], ...] = (
            (
                {
                    "a": 1,
                    "b": 1234,
                    "c": [1234, 5678],
                    "d": {12: "34", 56: "78"},
                },
                (),
                False,
            ),
            (
                {
                    "a": "2",
                    "b": "5678",
                    "c": [5678, 1234],
                    "e": 114514,
                },
                (),
                True,
            ),
            (
                {
                    "a": b"3",
                    "b": "9012",
                    "c": ["5678", 1234],
                    "d": {11: "aa", "bb": 22},
                },
                (
                    VerifyTypeError("dict_obj['a']", Union[int, str], b"3"),
                    VerifyTypeError("dict_obj['b']", Literal[1234, "5678"], "9012"),
                    VerifyTypeError("dict_obj['c'][0]", int, "5678"),
                    VerifyTypeError("dict_obj['d']['bb']", int, "bb"),
                    VerifyTypeError("dict_obj['d']['bb']", str, 22),
                ),
                False,
            ),
            (
                {
                    "b": 1234,
                    "c": [1234, 5678],
                    "d": {12: "34", 56: "78"},
                    "e": 114514,
                },
                (
                    VerifyKeyError("dict_obj", "a", "missing"),
                    VerifyKeyError("dict_obj", "e", "leftover"),
                ),
                False,
            ),
        )
        # TypedDict
        for typed_dict in available_typeddict:
            for dict_obj, exp_errs, allow_unexp_keys in cases:
                vaild = not exp_errs
                with self.subTest(typeddict_source=typed_dict.__module__, vaild=vaild):

                    class ATypedDict(typed_dict):  # type: ignore[misc, valid-type]
                        a: Union[int, str]
                        b: Literal[1234, "5678"]
                        c: List[int]
                        d: NotRequired[Dict[int, str]]  # type: ignore[valid-type]

                    if vaild:
                        self.assertFalse(
                            tuple(
                                check_dict(
                                    dict_obj, ATypedDict, "dict_obj", allow_unexp_keys
                                )
                            )
                        )
                        assert_dict(dict_obj, ATypedDict, "dict_obj", allow_unexp_keys)
                    else:
                        self.assertEqual(
                            tuple(
                                check_dict(
                                    dict_obj, ATypedDict, "dict_obj", allow_unexp_keys
                                )
                            ),
                            exp_errs,
                        )
                        with self.assertRaises((VerifyKeyError, VerifyTypeError)) as cm:
                            assert_dict(
                                dict_obj, ATypedDict, "dict_obj", allow_unexp_keys
                            )
                        self.assertEqual(cm.exception, exp_errs[0])
        # dict
        structure = {
            "a": Union[int, str],
            "b": Literal[1234, "5678"],
            "c": List[int],
            "d": NotRequired[Dict[int, str]],  # pyright: ignore
        }
        for dict_obj, exp_errs, allow_unexp_keys in cases:
            vaild = not exp_errs

            if vaild:
                self.assertFalse(
                    tuple(check_dict(dict_obj, structure, "dict_obj", allow_unexp_keys))
                )
                assert_dict(dict_obj, structure, "dict_obj", allow_unexp_keys)
            else:
                self.assertEqual(
                    tuple(
                        check_dict(dict_obj, structure, "dict_obj", allow_unexp_keys)
                    ),
                    exp_errs,
                )
                with self.assertRaises((VerifyKeyError, VerifyTypeError)) as cm:
                    assert_dict(dict_obj, structure, "dict_obj", allow_unexp_keys)
                self.assertEqual(cm.exception, exp_errs[0])
