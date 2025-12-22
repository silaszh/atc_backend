from server.server import app, socketio

if __name__ == "__main__":
    # 启动Flask应用（socket服务器已在server模块中启动）
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)