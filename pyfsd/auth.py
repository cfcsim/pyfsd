from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Callable, List, Tuple, Type

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernameHashedPassword
from twisted.cred.error import LoginFailed, UnauthorizedLogin, UnhandledCredentials
from twisted.cred.portal import IRealm
from twisted.internet.defer import Deferred
from zope.interface import Attribute, Interface, implementer

from .db_tables import users

if TYPE_CHECKING:
    from alchimia.engine import TwistedResultProxy

__all__ = ["CredentialsChecker", "Realm"]


class IUserInfo(Interface):
    name = Attribute("name")
    rating = Attribute("rating")


@implementer(IUserInfo)
@dataclass
class UserInfo:
    name: str
    rating: int


@implementer(IUsernameHashedPassword)
class UsernameSHA256Password:
    username: str
    password: str

    def __init__(self, username: str, unhashed_password: str) -> None:
        self.username = username
        self.password = sha256(unhashed_password.encode()).hexdigest()

    def checkPassword(self, hashed_password: str) -> bool:
        return hashed_password == self.password


@implementer(ICredentialsChecker)
class CredentialsChecker:
    credentialInterfaces = (IUsernameHashedPassword,)
    sql: str
    runQuery: Callable[..., Deferred]

    def __init__(
        self,
        runQuery: Callable[..., Deferred],
    ) -> None:
        self.runQuery = runQuery

    def requestAvatarId(self, credentials: UsernameSHA256Password) -> Deferred:
        if not IUsernameHashedPassword.providedBy(credentials):
            raise UnhandledCredentials()
        deferred: Deferred = Deferred()

        def callback(proxy: "TwistedResultProxy") -> None:
            proxy.fetchall().addCallbacks(
                self._cbAuthenticate,
                self._ebAuthenticate,
                callbackArgs=(credentials, deferred),
                errbackArgs=(credentials, deferred),
            )

        self.runQuery(
            users.select(users.c.callsign == credentials.username)
        ).addCallbacks(
            callback,
            self._ebAuthenticate,
            errbackArgs=(credentials, deferred),
        )
        return deferred

    def _cbAuthenticate(
        self,
        result: List[Tuple[str, str, int]],
        credentials: UsernameSHA256Password,
        deferred: Deferred,
    ) -> None:
        if len(result) == 0:
            deferred.errback(UnauthorizedLogin("Username unknown"))
        else:
            hashed_password = result[0][1]
            if IUsernameHashedPassword.providedBy(credentials):
                if credentials.checkPassword(hashed_password):
                    deferred.callback((credentials.username, result[0][2]))
                else:
                    deferred.errback(UnauthorizedLogin("Password mismatch"))
            else:
                deferred.errback(UnhandledCredentials())

    def _ebAuthenticate(
        self, message: str, _: UsernameSHA256Password, deferred: Deferred
    ) -> None:
        deferred.errback(LoginFailed(message))


@implementer(IRealm)
class Realm:
    @staticmethod
    def requestAvatar(
        result: Tuple[str, int], _: None, *interfaces: Type[Interface]
    ) -> Tuple[Type[IUserInfo], UserInfo, Callable]:
        if IUserInfo in interfaces:
            return IUserInfo, UserInfo(*result), lambda: None
        else:
            raise NotImplementedError("no interface")
