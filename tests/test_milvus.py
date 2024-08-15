from pymilvus import connections

# Connection details
host = "in01-290b846206157f0.aws-us-west-2.vectordb.zillizcloud.com"
port = "19536"
user = "db_admin"
password = "Eg1^Xb=fDUfWG-c["

try:
    # Attempt to connect
    connections.connect(
        alias="default", 
        host=host, 
        port=port,
        user=user,
        password=password,
        secure=True
    )
    print("Successfully connected to Zilliz!")

    # List collections (if any)
    from pymilvus import utility
    collections = utility.list_collections()
    print("Collections:", collections)

    # Disconnect
    connections.disconnect("default")
    print("Disconnected from Zilliz.")

except Exception as e:
    print(f"Failed to connect: {e}")