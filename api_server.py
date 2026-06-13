from app_factory import create_app

app = create_app(enable_cors=True)

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5050, threads=8)
