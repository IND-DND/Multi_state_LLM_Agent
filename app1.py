
import streamlit as st

from graph.workflow import app




st.set_page_config(
    page_title="Multi-State LLM Sales Agent",
    layout="wide"
)




st.title(
    "Multi-State LLM Agent for SQL and Data Visualization"
)

st.write(
    "Ask questions about your sales database using natural language."
)




if "history" not in st.session_state:

    st.session_state.history = []




question = st.text_input(
    "Enter your question:"
)




if st.button("Run Query"):

    if not question:

        st.warning(
            "Please enter a question."
        )

    else:

        # Initial LangGraph state
        initial_state = {

            "user_question": question,

            "intent": None,

            "sql_query": None,

            "query_result": None,

            "visualization_type": None,

            "figure": None,

            "error": None,

            "conversation_history":
                st.session_state.history
        }


        

        result = app.invoke(
            initial_state
        )



        st.session_state.history.append(
            {
                "question": question,

                "sql": result.get(
                    "sql_query",
                    ""
                )
            }
        )


       

        st.subheader(
            "NLP Agent Output"
        )

        st.write(
            result.get(
                "intent",
                "No NLP output available."
            )
        )



        st.subheader(
            "Generated SQL Query"
        )

        st.code(
            result.get(
                "sql_query",
                ""
            ),
            language="sql"
        )


    

        if result.get("error"):

            st.error(
                result["error"]
            )


        else:

            

            st.subheader(
                "Query Result"
            )

            query_result = result.get(
                "query_result"
            )


            if query_result is not None:

                st.dataframe(
                    query_result,
                    use_container_width=True
                )

            else:

                st.info(
                    "No query results returned."
                )


           

            st.subheader(
                "Visualization"
            )


            figure = result.get(
                "figure"
            )


            visualization_type = result.get(
                "visualization_type",
                "none"
            )


            if figure is not None:

                st.write(
                    f"Chart Type: {visualization_type.title()}"
                )

                st.plotly_chart(
                    figure,
                    use_container_width=True
                )


            else:

                st.info(
                    "No visualization was generated for this query."
                )




if st.session_state.history:

    st.sidebar.subheader(
        "Conversation History"
    )


    for item in st.session_state.history:

        st.sidebar.write(
            f"Question: {item['question']}"
        )

        st.sidebar.code(
            item["sql"],
            language="sql"
        )

