from flask import Flask, render_template, request

from graph.workflow1 import app as workflow

app2 = Flask(__name__)

@app2.route("/",methods=["GET","POST"])

def home():

    sql = ""

    result = ""

    if request.method == "POST":

        question = request.form.get("question") or request.form.get("query")

        if question:
            response = workflow.invoke({
                "question": question
            })

            sql = response.get("sql", "")
            result = response.get("result", "")
        else:
            result = "No question provided. Please enter a question."

    return render_template(

        "app2_index.html",

        sql=sql,

        result=result

    )

if __name__=="__main__":

    app2.run(debug=True)