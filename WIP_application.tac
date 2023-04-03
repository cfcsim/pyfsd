def makeApplication(
    client_strport: str, uid: Optional[int] = None, gid: Optional[int] = None
) -> "Componentized":
    app = Application("PyFSD", uid=uid, gid=gid)
    pyfsd = PyFSDService()
    serviceCollection = IServiceCollection(app)
    pyfsd.setServiceParent(serviceCollection)
    service(client_strport, pyfsd.makeClientFactory()).setServiceParent(
        serviceCollection
    )
    return app
