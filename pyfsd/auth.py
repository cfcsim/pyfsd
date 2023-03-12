from hashlib import md5
from typing import Callable, List, Tuple

from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernameHashedPassword
from twisted.cred.error import LoginFailed, UnauthorizedLogin, UnhandledCredentials
from twisted.cred.portal import IRealm
from twisted.internet.defer import Deferred
from zope.interface import implementer

__all__ = ["CredentialsChecker", "Realm"]


@implementer(IUsernameHashedPassword)
class UsernameMD5Password:
    username: str
    password: str

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = md5(password.encode()).hexdigest()

    def checkPassword(self, password: str) -> bool:
        return password == self.password


@implementer(ICredentialsChecker)
class CredentialsChecker:
    credentialInterfaces = (IUsernameHashedPassword,)
    sql: str
    runQuery: Callable[[str, tuple], Deferred]

    def __init__(
        self,
        runQuery: Callable[[str, tuple], Deferred],
        query: str = "SELECT callsign, password FROM user WHERE callsign = ?",
    ) -> None:
        self.runQuery = runQuery
        self.sql = query

    def requestAvatarId(self, credentials: UsernameMD5Password) -> Deferred:
        if not IUsernameHashedPassword.providedBy(credentials):
            raise UnhandledCredentials()
        dbDeferred: Deferred = self.runQuery(self.sql, (credentials.username,))
        deferred: Deferred = Deferred()
        dbDeferred.addCallbacks(
            self._cbAuthenticate,
            self._ebAuthenticate,
            callbackArgs=(credentials, deferred),
            errbackArgs=(credentials, deferred),
        )
        return deferred

    def _cbAuthenticate(
        self,
        result: List[Tuple[str, str]],
        credentials: UsernameMD5Password,
        deferred: Deferred,
    ) -> None:
        if len(result) == 0:
            deferred.errback(UnauthorizedLogin("Username unknown"))
        else:
            hashed_password = result[0][1]
            if IUsernameHashedPassword.providedBy(credentials):
                if credentials.checkPassword(hashed_password):
                    deferred.callback(credentials.username)
                else:
                    deferred.errback(UnauthorizedLogin("Password mismatch"))
            else:
                deferred.errback(UnhandledCredentials())

    def _ebAuthenticate(self, message: str, _, deferred: Deferred):
        deferred.errback(LoginFailed(message))


@implementer(IRealm)
class Realm:
    def requestAvatar(*args):
        print(args)
