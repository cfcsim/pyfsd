from typing import List, Tuple, Type, Union

__all__ = [
    "explainType",
    "UnionType",
    "LiteralValue",
    "UnionType",
    "MayExist",
    "ConfigKeyError",
    "ConfigTypeError",
    "ConfigValueError",
    "verifyConfigStruct",
    "verifyAllConfigStruct",
]


def explainType(obj: object) -> str:
    if isinstance(obj, type):
        return f"literally {obj.__name__}"
    elif isinstance(obj, dict):
        return str(obj)
    else:
        return type(obj).__name__


class UnionType:
    types: Tuple[Union[Type, dict], ...]

    def __init__(self, *args: Union[Type, dict]) -> None:
        have_dict = False
        for arg in args:
            if not isinstance(arg, (type, dict)):
                raise TypeError(
                    "UnionType(arg, ...): arg must be a type or dict. "
                    f"Got {arg!r:.100}."
                )
            elif isinstance(arg, dict):
                assert not have_dict
                have_dict = True
        self.types = args

    def __class_getitem__(cls, *args: Union[Type, dict]) -> "UnionType":
        return cls(*args)

    def __repr__(self) -> str:
        def explain(type_: Union[Type, dict]) -> str:
            if isinstance(type_, type):
                return type_.__name__
            elif isinstance(type_, dict):
                return repr(type_)
            else:
                raise RuntimeError(f"Invaild type: {type_!r}")

        return f"UnionType({', '.join(explain(type_) for type_ in self.types)})"

    def __str__(self) -> str:
        return " or ".join(
            type_.__name__ if isinstance(type_, type) else repr(type_)
            for type_ in self.types
        )

    def __eq__(self, another: object) -> bool:
        return isinstance(another, UnionType) and another.types == self.types


class LiteralValue:
    values: Tuple[object, ...]

    def __init__(self, *args: object) -> None:
        self.values = args

    def __class_getitem__(cls, *args: object) -> "LiteralValue":
        return cls(*args)

    def __repr__(self) -> str:
        return f"LiteralValue{self.values!r}"

    def __str__(self) -> str:
        return "literally " + " or ".join(str(value) for value in self.values)

    def __eq__(self, another: object) -> bool:
        return isinstance(another, LiteralValue) and another.values == self.values


class MayExist:
    type: Union[Type, dict, UnionType, LiteralValue]

    def __init__(self, arg: Union[Type, dict, UnionType, LiteralValue]) -> None:
        if not isinstance(arg, (type, dict, UnionType, LiteralValue)):
            raise TypeError(
                "MayExist(arg): arg must be a type or dict or UnionType or "
                f"LiteralValue. Got {arg!r}."
            )
        self.type = arg

    def __class_getitem__(
        cls, arg: Union[Type, dict, UnionType, LiteralValue]
    ) -> "MayExist":
        return cls(arg)

    def __repr__(self) -> str:
        name = self.type.__name__ if isinstance(self.type, type) else repr(self.type)
        return f"MayExist({name})"

    def __str__(self) -> str:
        if isinstance(self.type, (UnionType, LiteralValue, dict)):
            return str(self.type)
        else:
            return self.type.__name__

    def __eq__(self, another: object) -> bool:
        return isinstance(another, MayExist) and another.type == self.type


class ConfigKeyError(KeyError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(name)


class ConfigValueError(ValueError):
    name: str
    excepted: LiteralValue
    actually: object

    def __init__(self, name: str, excepted: LiteralValue, actually: object) -> None:
        self.name = name
        self.excepted = excepted
        self.actually = actually
        super().__init__(name, (excepted, actually))

    def __str__(self) -> str:
        return f"'{self.name}' must be {self.excepted}, not {self.actually}"


class ConfigTypeError(TypeError):
    name: str
    excepted: Union[Type, UnionType, dict]
    actually: object

    def __init__(
        self, name: str, excepted: Union[Type, UnionType, dict], actually: object
    ) -> None:
        self.name = name
        self.excepted = excepted
        self.actually = actually
        super().__init__(name, (excepted, actually))

    def __str__(self) -> str:
        if isinstance(self.excepted, type):
            type_ = self.excepted.__name__
        elif isinstance(self.excepted, UnionType):
            type_ = str(self.excepted)
        elif isinstance(self.excepted, dict):
            type_ = str(self.excepted)
        else:
            raise RuntimeError(f"Invaild type: {self.excepted!r}")
        return f"'{self.name}' must be {type_}, not {explainType(self.actually)}"


def verifyConfigStruct(config: dict, structure: dict, prefix: str = "") -> None:
    for key, type_ in structure.items():
        try:
            value = config[key]
        except KeyError:
            if isinstance(type_, MayExist):
                continue
            else:
                raise ConfigKeyError(f"{prefix}{key}")
        else:
            if isinstance(type_, MayExist):
                true_type = type_.type
            else:
                true_type = type_

        if isinstance(true_type, type):
            if not isinstance(value, true_type):
                raise ConfigTypeError(f"{prefix}{key}", type_, value)
        elif isinstance(true_type, dict):
            if not isinstance(config[key], dict):
                raise ConfigTypeError(f"{prefix}{key}", type_, value)
            verifyConfigStruct(value, true_type, prefix=f"{prefix}{key}.")
        elif isinstance(true_type, LiteralValue):
            if value not in true_type.values:
                raise ConfigValueError(f"{prefix}{key}", type_, value)
        elif isinstance(true_type, UnionType):
            succeed = False
            for may_type in true_type.types:
                if isinstance(may_type, type):
                    if isinstance(value, may_type):
                        succeed = True
                        break
                elif isinstance(may_type, dict):
                    if isinstance(value, dict):
                        verifyConfigStruct(value, may_type, prefix=f"{prefix}{key}.")
                        succeed = True
                        break
            if not succeed:
                raise ConfigTypeError(f"{prefix}{key}", type_, value)
        else:
            raise TypeError(f"Invaild type: {explainType(type_)}")


def verifyAllConfigStruct(
    config: dict, structure: dict, prefix: str = ""
) -> Tuple[Union[ConfigKeyError, ConfigTypeError, ConfigValueError], ...]:
    errors: List[Union[ConfigKeyError, ConfigTypeError, ConfigValueError]] = []
    for key, type_ in structure.items():
        try:
            value = config[key]
        except KeyError:
            if not isinstance(type_, MayExist):
                errors.append(ConfigKeyError(f"{prefix}{key}"))
            continue
        else:
            if isinstance(type_, MayExist):
                type_ = type_.type
        if isinstance(type_, type):
            if not isinstance(value, type_):
                errors.append(ConfigTypeError(f"{prefix}{key}", type_, value))
        elif isinstance(type_, dict):
            if not isinstance(config[key], dict):
                errors.append(ConfigTypeError(f"{prefix}{key}", type_, value))
            else:
                errors.extend(
                    verifyAllConfigStruct(value, type_, prefix=f"{prefix}{key}.")
                )
        elif isinstance(type_, LiteralValue):
            if value not in type_.values:
                errors.append(ConfigValueError(f"{prefix}{key}", type_, value))
        elif isinstance(type_, UnionType):
            succeed = False
            for may_type in type_.types:
                if isinstance(may_type, type):
                    if isinstance(value, may_type):
                        succeed = True
                        break
                elif isinstance(may_type, dict):
                    if isinstance(value, dict):
                        verifyConfigStruct(value, may_type, prefix=f"{prefix}{key}.")
                        succeed = True
                        break
            if not succeed:
                errors.append(ConfigTypeError(f"{prefix}{key}", type_, value))
        else:
            raise TypeError(f"Invaild type: {explainType(type_)}")
    return tuple(errors)
