from openai import OpenAI
import os
from helperfunctions import clean_text,process_text,getlogger
from intro_full_text_metadata import process_df,client
import re

class Processhtmltext:
    client = OpenAI(api_key=os.getenv("OPENAI_SECRET_KEY"))
    def __init__(self,text,max_words,max_tokens) -> None:
        self.text=text
        self.logger=getlogger("simplelog.log")
        self.max_words=max_words
        self.max_tokens=max_tokens

    def _process_html_text(self):
        cleaned_string = re.sub(r'\n\s*\n', '\n', self.text)
        text=clean_text(fulltext=cleaned_string,logger=self.logger,max_words=self.max_words)
        df=process_text(text=text,logger=self.logger,max_tokens=self.max_tokens)
        df=process_df(df=df,logger=self.logger)
        data=str(df["text"][0])
        metadata = data.replace('\\n\\n', '\n\n')
        dict_response = {item.split(':', 1)[0]: item.split(':', 1)[1].strip() for item in metadata.split("\n\n") if ':' in item}
        return dict_response
    

if __name__=="__main__":
    html_text=""
    obj=Processhtmltext(text=html_text,max_tokens=500,max_words=1000)
    print(obj._process_html_text())
