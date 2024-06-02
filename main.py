import streamlit as st
import requests
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Function to get data from the API
def get_submissions(api_key, url="https://cfp.pycon.my/api/events/pyconmy-2024/submissions/"):
    headers = {"Authorization": f"Token {api_key}"}
    response = requests.get(url, headers=headers)
    return response.json()

def get_reviews(api_key, url="https://cfp.pycon.my/api/events/pyconmy-2024/reviews/"):
    headers = {"Authorization": f"Token {api_key}"}
    response = requests.get(url, headers=headers)
    return response.json()

def convert_datetime(date):
    original_datetime = datetime.fromisoformat(date)
    formatted_datetime_str = original_datetime.strftime("%d/%m/%y %H:%M:%S")
    return formatted_datetime_str

def show_submissions_in_table(data, api_key):
    submissions = data['results']
    submission_data = []
    for submission in submissions:
        submission_data.append({
            "Code": submission["code"],
            "Type": submission["submission_type"]["en"],
            "Title": submission["title"],
            "Submission Date": submission["created"],
        })
    # Handle pagination if 'next' is available
    next_url = data.get('next')
    while next_url:
        next_data = get_submissions(api_key, next_url)
        submissions = next_data['results']
        for submission in submissions:
            submission_data.append({
                "Code": submission["code"],
                "Type": submission["submission_type"]["en"],
                "Title": submission["title"],
                "Submission Date": submission["created"],
            })
        next_url = next_data.get('next')

    # Update the DataFrame and display it
    df = pd.DataFrame(submission_data)
    df['Submission Date'] = pd.to_datetime(df['Submission Date'])
    df = df.sort_values(by='Submission Date')
    df['Submission Date'] = df['Submission Date'].dt.strftime("%d/%m/%y %H:%M:%S")

    df.reset_index(drop=True, inplace=True)
    df.index = df.index + 1

    # Add clickable links
    df['Code'] = df['Code'].apply(lambda x: f'<a href="?code={x}">{x}</a>')
    return df

def show_submission_details(api_key, code):
    url = f"https://cfp.pycon.my/api/events/pyconmy-2024/submissions/{code}/"
    data = get_submissions(api_key, url)
    return data

def show_reviews_for_submission(api_key, code):
    reviews_data = []
    url = "https://cfp.pycon.my/api/events/pyconmy-2024/reviews/"
    while url:
        data = get_reviews(api_key, url)
        reviews_data.extend(data['results'])
        url = data.get('next')

    submission_reviews = [review for review in reviews_data if review['submission'] == code]
    return submission_reviews

def calling_gemini(model,abstract, description, reviews):
    response = model.generate_content(f'You are looking at a conference submission and the reviews given by different reviewers. The abstract of the submission is {abstract}, and description is {description}. The reviewer comments are: {", ".join(reviews)}. Also, provide your final score in scale of 0 to 2, where 0 is unacceptable, while 2 is acceptable.')
    return response

st.set_page_config(layout='wide')
st.title("PyCon MY 2024 Submissions")

#api_key = os.getenv("PRETALX_API")
api_key = st.secrets['PRETALX_API']
gemini_key = st.secrets['GEMINI_API']
#gemini_key=os.getenv('GEMINI_API')

genai.configure(api_key=gemini_key)
model = genai.GenerativeModel('gemini-1.5-flash')

# Check if a code query parameter is present
query_params = st.experimental_get_query_params()
code = query_params.get('code', [None])[0]

if code:
    # Show details for the specific submission
    submission_data = show_submission_details(api_key, code)
    st.header(f"Details for Submission Code: `{code}`")
    st.markdown(f"## Title: {submission_data['title']}")
    st.markdown("### Abstract")
    st.markdown(submission_data['abstract'])
    st.markdown("### Description")
    st.markdown(submission_data['description'])
    st.markdown("---")

    reviews = show_reviews_for_submission(api_key, code)
    st.subheader("Reviewer Comments")
    score = 0
    reviewer = 0
    comments = []
    for review in reviews:
        st.markdown(f"""
        **Reviewer:** {review['user']}  
        **Score:** {review['score']}  
        **Comment:** {review['text']}  
        """)
        comments.append(review['text'])
        score += float(review['score'])
        reviewer +=1
        st.markdown("---")
    st.markdown(f"## Total Score from {reviewer} reviewers: {score}. Average Score: {score/reviewer:.2f}")
    st.markdown("---")
    st.markdown("## From Gemini")
    response = calling_gemini(model,submission_data['abstract'],submission_data['description'],comments)
    try:
        st.markdown(response.text)
    except Exception as e:
        st.markdown(f'{type(e).__name__}: {e}')

else:
    # Show the submissions table
    data = get_submissions(api_key)

    count = data['count']
    st.metric(label="Total Submissions", value=count)

    df = show_submissions_in_table(data, api_key)
    st.markdown(df.to_html(escape=False, index=False).replace('<th>', '<th align="left">'), unsafe_allow_html=True)
