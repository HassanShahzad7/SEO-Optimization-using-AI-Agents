import configparser
import os
import json

config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))


def promts_dict(key, context, h1_title, metadesc, title):
    prompts = {
        
        6: [
            {
                "role": "user",
                "content": f"""
You are a helpful SEO consultant with knowledge of how SEO keywords and tags impact search results and how to identify them within a 
given context. The requirement is to create keywords, meta tags, meta description, title tag and H1 tag for an article within the 
Linux and open source context for an infosec professional audience.

Definitions:
Linux Security: Linux security refers to the set of practices and measures used to protect Linux-based operating systems from 
various security threats and vulnerabilities. Linux is a widely used open-source operating system that has gained popularity due 
to its security features, stability, and flexibility.

Tags: High-level words within the Linux security and open source context that is directly related to the provided content. 
Tags are formed based only on the specific topic being discussed in the provided content.

Meta Keywords: Meta keywords are specific meta tags located in the HTML head section of a webpage containing a list of keywords that 
represent the content of the page for search engines.

Title Tag: A title tag (or <title> tag) is an HTML element that provides a webpage title for search engines and internet browsers 
to use. It can appear in search engine results and link previews for the pages.

H1 Tag: An H1 tag is the HTML used to create the main title on a webpage and helps indicate the page’s primary topic to visitors 
and search engines. It contains an opening <h1> tag, the title text, and a closing </h1> tag.

Please follow these instructions explicitly, step by step.
1.  Extract 3-5 meta keywords relevant to the context without using overly generic terms relevant to the article's context, focusing 
on high-volume terms.
2.  Create a list of 5-7 relevant high-volume tags based on the specified criteria within the given Linux security context, focusing 
on the specific topics of interest directly related to the content. Use "{title}" and "{h1_title}" to provide useful content as a basis
 for your Tag. Tags must not include phrases including "Linux security" or "open source" or "open source security" or "cybersecurity" 
 or "network security" that would apply to any article within the Linux security context. Tags must be case-insensitive, singular form,
 and use natural English words without underscores or hyphens.
3.  Compose a concise meta description summarizing the article's content within a 20-word limit.
4.  Create a title tag under 60 characters or 7 words, following SEO practices. For "Advisory" content, use unique terms 
(e.g., SLE-15-SP4, CVE numbers, ELSA identifiers) from the article for distinction and ensure it's different from any H1 tag. 
If applicable, include the application name with its version (e.g., gdk-pixbuf2-2.42.6-4). Use "{title}" to reflect the content 
accurately and uniquely. Title tag must not be the same as "{h1_title}" or "{title}".
5.  Generate an H1 tag according to SEO best practices. Title and H1 tags must not be the same. H1 Tag can be no longer than 8 words 
or 80 characters. H1 Tag should be very descriptive and contain more detail about the article than title tags. H1 tags should be close 
to the main synopsis of the article. Use "{title}" to provide useful content as a basis for your H1 tag to make it unique. H1 tag must
 not be the same as "{h1_title}" or "{title}".
6.  Identify the type of article as one of Advisory, which is content related to a security update of some kind, or Feature, which is 
a piece of news or a story that digs deep on a particular topic.

###
Given Content: {context}
###
Example Output:
{{
    "Keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "Description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not 
    exceeding 160 characters.",
    "Tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6", "Tag7" ],
    "Title": "Linux Security Article Title",
    "H1": "Linux Security H1 Tag",
    "Type": "Feature or Advisory"
}}
###
JSON Output:
"""
            }
        ],
    }

    return prompts[key]


gpt_model = {
    1: "gpt-3.5-turbo-1106",
    2: "gpt-4",
    3: "gpt-3.5-turbo",
    4: "gpt-4o mini"
}


def get_model():
    get_gpt_model = config.get("chatgpt", "gpt_model")
    model = int(get_gpt_model[0]) if get_gpt_model else 1
    try:
        return gpt_model.get(model)
    except Exception as e:
        print(e)


def get_prompt(context, h1_title:str="", metadesc:str="", title:str=""):
    get_prompt_key = config.get("chatgpt", "prompt_key")
    prompt_key = int(get_prompt_key) if get_prompt_key else 1
    try:
        # dave print("Prompt key used  : ", prompt_key)
        prompt = promts_dict(prompt_key, context, h1_title, metadesc, title)
        return prompt
    except Exception as e:
        print(e)