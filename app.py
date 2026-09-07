from flask import Flask, render_template, request
from llm.chatbot import chatbot

app = Flask(__name__)

@app.route("/", methods=["GET","POST"])
def home():

    answer=""

    if request.method=="POST":

        question=request.form["query"]

        answer=chatbot(question)

    return render_template("index.html",answer=answer)

if __name__=="__main__":
    app.run(debug=True)