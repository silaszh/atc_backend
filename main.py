from server.server import app

if __name__ == "__main__":
    # 启动Flask应用（socket服务器已在server模块中启动）
    app.run(host="0.0.0.0", port=5000, debug=True)