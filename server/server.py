from flask import Flask

# 设置静态文件目录
app = Flask(__name__, static_folder="../static", static_url_path="/")


@app.route("/", methods=["GET"])
def index():
    return app.send_static_file("index.html")


@app.errorhandler(404)
def page_not_found(e):
    return app.send_static_file("index.html")


from .routes.model import bp as model_bp
from .routes.seat import bp as seat_bp
from .routes.state import bp as state_bp
from .ws_service import socketio as wss

wss.init_app(app)

app.register_blueprint(model_bp)
app.register_blueprint(seat_bp)
app.register_blueprint(state_bp)
