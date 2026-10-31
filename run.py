from app import create_app

app = create_app()
print("MAIL:", app.config["MAIL_SERVER"], app.config["MAIL_PORT"],
      app.config["MAIL_USE_SSL"], app.config["MAIL_USE_TLS"])

if __name__ == "__main__":
    app.run(debug=True)

