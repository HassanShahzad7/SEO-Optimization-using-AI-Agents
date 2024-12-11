import configparser
import os
import json
from langchain_openai import ChatOpenAI
from log_handler import log_error as log_if_error, log_info

config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))


def promts_dict(key, context, h1_title, metadesc, title):
    prompts = {
        1: f""" Instructions:
            1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
            2. Extract 5 to 10 high-volume Meta keywords and meta tags from the given context.
            3. Create a concise Meta description that summarizes the given context, ensuring that the Meta description's word length does not exceed 20 words.
            4. If the Meta description's word length exceeds 20 words, trim it to meet the limit.
            5. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
            6. The Meta keywords, meta tags, and Meta description must be strictly derived from the provided context, aligning with SEO best practices.
            7. Ensure that each Meta keyword is distinct from the others.
            8. Extract Meta tags that reflect key concepts and terms from the text, focused on infosecurity and Linux server management.
            9. Ensure these tags are specific, with each tag being a single impactful word or multiple authoritative words.
            10. List these tags in a format within brackets and separated by commas.
            11. Tags should be unique, relevant, and derived strictly from the content provided.
            12. Meta keywords and Tags must be unique from each other or similar but not exactly the same.
            13. Avoid words common to all content related to Linux and open source, including "linux" and "open source" and "cybersecurity".
            14. Results must be suitable for a Linux and info security professional audience who are generally highly-educated and experienced Linux sysadmins.
            15. The collection of meta tags should strictly relate to the context.
            16. Strictly adhere to SEO best practices in generating accurate Meta data for websites.
            17. Tags should be chosen for their low keyword difficulty and high search volume, relevant for boosting search engine visibility.
            18. Create primary single-word tags that are central to the themes of Linux, open source, infosecurity, and Linux server management.
            19. Keywords and tags must not be the same.
            20 . Strictly follow these steps:
                    1. Read all the previous process context.
                    2 .Check if the tags are similar to the last data (all processed data).
                    3 . Ensure the tags are general and valid. For example, use "Security Advisory" instead of a specific term like "Red Hat Security Advisory." Always apply this rule
                    4.Maintain the state of the conversation, including user preferences, prior questions, and given answers.
                


            - Keywords: high-level words or phrases that capture the primary topics and themes of the content.
            - Tags: low-level general labels that categorize the content into specific themes. These help with site navigation and categorizing content. Tags provide details that the keywords don’t convey, so it’s handy to use them together. 

            After creating tags and keywords for this context, review above instructions again to ensure you have not used words like "linux" and "open source" and "cybersecurity" in your results.

            ###
            Given Context: {context}"""
        # [
        # {
        #             "role": "system",
        #             "content": "You are an SEO expert. Analyze the given context from a website for Linux and open-source security professionals to create meta tags, meta keywords, and a concise meta description for SEO purposes. Provide structured JSON output with the top 5 to 8 Meta keywords, meta tags, and the Meta description. The Meta description should be up to 20 words long. Ensure the Meta keywords are distinct, surrounded by quotes, and relevant to the given context."
        # },
        #                 {
        #                     "role": "user",
        #                     "content": f"""
        #     Instructions:
        #     1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
        #     2. Extract 5 to 10 high-volume Meta keywords and meta tags from the given context.
        #     3. Create a concise Meta description that summarizes the given context, ensuring that the Meta description's word length does not exceed 20 words.
        #     4. If the Meta description's word length exceeds 20 words, trim it to meet the limit.
        #     5. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
        #     6. The Meta keywords, meta tags, and Meta description must be strictly derived from the provided context, aligning with SEO best practices.
        #     7. Ensure that each Meta keyword is distinct from the others.
        #     8. Extract Meta tags that reflect key concepts and terms from the text, focused on infosecurity and Linux server management.
        #     9. Ensure these tags are specific, with each tag being a single impactful word or multiple authoritative words.
        #     10. List these tags in a format within brackets and separated by commas.
        #     11. Tags should be unique, relevant, and derived strictly from the content provided.
        #     12. Meta keywords and Tags must be unique from each other or similar but not exactly the same.
        #     13. Avoid words common to all content related to Linux and open source, including "linux" and "open source" and "cybersecurity".
        #     14. Results must be suitable for a Linux and info security professional audience who are generally highly-educated and experienced Linux sysadmins.
        #     15. The collection of meta tags should strictly relate to the context.
        #     16. Strictly adhere to SEO best practices in generating accurate Meta data for websites.
        #     17. Tags should be chosen for their low keyword difficulty and high search volume, relevant for boosting search engine visibility.
        #     18. Create primary single-word tags that are central to the themes of Linux, open source, infosecurity, and Linux server management.
        #     19. Keywords and tags must not be the same.
        #     Difference between "keywords" and "tags":
        #     - Keywords: high-level words or phrases that capture the primary topics and themes of the content.
        #     - Tags: low-level general labels that categorize the content into specific themes. These help with site navigation and categorizing content. Tags provide details that the keywords don’t convey, so it’s handy to use them together.
        #     After creating tags and keywords for this context, review above instructions again to ensure you have not used words like "linux" and "open source" and "cybersecurity" in your results.
        #     ###
        #     Given Context: {context}
        #     ###
        #     Example Output:
        #     {{
        #         "Meta keywords": ["Keyword1", "Keyword2", "Keyword3"],
        #         "Meta description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 160 characters.",
        #         "Tags": ["Tag1", "Tag2", "Tag3"]
        #     }}
        #     ###
        #     JSON Output:
        #     """
        #         }
        #     ],
        ,
        2: [
            {
                "role": "system",
                "content": "Act as an SEO specialist and analyze the given context to identify Meta keywords and create a concise Meta description for SEO purposes. The Meta description should be up to 20 Words long. Ensure the Meta keywords are distinct, surrounded by quotes, and relevant to the given context. Provide a structured JSON output with the top 5 to 8 Meta keywords and the Meta description. Emphasize the importance of SEO best practices in generating accurate Meta data for websites.                     Analyze the provided text related to text. Identify key single-word tags that are central to the themes of security updates and Linux server management.These tags should be chosen for their low difficulty and high search volume, relevant for boosting search engine visibility ",
            },
            {
                "role": "user",
                "content": f"""Instructions:
    1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
    2. Extract 5 to 10 high volume Meta keywords from the given context.
    3. Create a consise Meta description that summarize the given context and ensure that the Meta descritpion Words length should not exceed the 20. 
    4. If the Meta description Words length is greater than 20 then trim the Meta descritpion that is more than 20 Words.
    4. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
    5. The Meta keywords and Meta description must be directly derived from the provided context, aligning with SEO best practices.

   6. Ensure that each Meta keyword is distinct from one another. The tags provided above are preferred, even if they consist of    multiple words.
    7.Clarified the objective: "Extract Meta tags that reflect key concepts and terms from the text, focusing on security and Linux server  management." This provides a clear direction for what the tags should represent.

    8. Ensure these tags are direct, with each tag being a single or multiple , impactful word.
    9.  Specified the format for listing tags: "List these tags in a format within brackets and separated by commas." This ensures consistency in how the tags are presented.like this: [Tag1, Tag2, Tag3].
    10. Reinforced the importance of uniqueness and relevance: "Tags should be unique, relevant, and derived strictly from the content provided." This emphasizes the quality criteria for the tags.
    ###

    Given Context: {context}

    ###

    Example Output:{{
    "Meta keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "Meta description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 160 characters.",
    "Tags" :[Tag1, Tag2, Tag3],
    }}
    ###


    JSON Output:""",
            },
        ],
        3: [
            {
                "role": "system",
                "content": "Act as an SEO specialist and analyze the given context to identify Meta keywords and create a concise Meta description for SEO purposes. The Meta description should be up to 20 Words long. Ensure the Meta keywords are distinct, surrounded by quotes, and relevant to the given context. Provide a structured JSON output with the top 5 to 8 Meta keywords and the Meta description. Emphasize the importance of SEO best practices in generating accurate Meta data for websites.                     Analyze the provided text related to text. Identify key single-word tags that are central to the themes of security updates and Linux server management.These tags should be chosen for their low difficulty and high search volume, relevant for boosting search engine visibility ",
            },
            {
                "role": "user",
                "content": f"""Instructions:
    1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
    2. Extract 5 to 10 high volume Meta keywords from the given context.
    3. Create a consise Meta description that summarize the given context and ensure that the Meta descritpion Words length should not exceed the 20. 
    4. If the Meta description Words length is greater than 20 then trim the Meta descritpion that is more than 20 Words.
    4. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
    5. The Meta keywords and Meta description must be directly derived from the provided context, aligning with SEO best practices.
    6. The Meta keywords and Meta description must be directly derived from the provided context, aligning with SEO best practices.

    7. Extract single-word Meta tags that reflect key concepts and terms from the text, focusing on security and Linux server management.
    8. Ensure these tags are direct, with each tag being a single, impactful word.
    9. List these tags in a format within brackets and separated by commas, like this: [Tag1, Tag2, Tag3].
    10. Tags should be unique, relevant, and derived strictly from the content provided.

 


    ###

    Given Context: {context}

    ###

    Example Output:{{
    "Meta keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "Meta description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 160 characters.",
    "Tags" :[Tag1, Tag2, Tag3],
    }}
    ###


    JSON Output:""",
            },
        ],
        4: [
            {
                "role": "system",
                "content": "Act as an SEO specialist and analyze the given context to identify Meta keywords and create a concise Meta description for SEO purposes. The Meta description should be up to 20 words long. Ensure the Meta keywords are distinct, surrounded by quotes, and relevant to the given context. Provide a structured JSON output with the top 5 to 8 Meta keywords and the Meta description. Emphasize the importance of SEO best practices in generating accurate Meta data for websites. Analyze the provided text related to the given context. Identify key single-word tags that are central to the themes of security updates and Linux server management. These tags should be chosen for their low difficulty and high search volume, relevant for boosting search engine visibility.",
            },
            {
                "role": "user",
                "content": f"""Instructions:
        1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
        2. Extract 5 to 10 high-volume Meta keywords from the given context.
        3. Create a concise Meta description that summarizes the given context, ensuring that the Meta description's word length does not exceed 20 words.
        4. If the Meta description's word length exceeds 20 words, trim it to meet the limit.
        5. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
        6. The Meta keywords and Meta description must be directly derived from the provided context, aligning with SEO best practices.
        7. Ensure that each Meta keyword is distinct from the others. The provided tags above are preferred, even if they consist of multiple words.
        8. Clarify the objective: "Extract Meta tags that reflect key concepts and terms from the text, focusing on security and Linux server management." This provides clear direction for what the tags should represent.
        9. Ensure these tags are direct, with each tag being a single impactful word or multiple impactful words and also the length of tags  is 5.
        10. Specify the format for listing tags: "List these tags in a format within brackets and separated by commas." This ensures consistency in how the tags are presented, like this: [Tag1, Tag2, Tag3].
        11. Reinforce the importance of uniqueness and relevance: "Tags should be unique, relevant, and derived strictly from the content provided." This emphasizes the quality criteria for the tags.
        12. Meta keywords and Tags must be unique from each other or similar but not exactly the same.
        13. Avoid using common words such as "Linux," "open source," and "security."
 
        Difference between "keywords" and "tags":
        - Keywords: Specific words or phrases that capture the primary topics and themes of the content. Used in Meta tags for SEO to improve search engine visibility.
        - Tags: General labels that categorize the content into broader themes. Help with site navigation and organizing content.
 
        ###
        Given Context: {context}
 
        ###
        Example Output:
        {{
            "Meta keywords": ["Keyword1", "Keyword2", "Keyword3"],
            "Meta description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 160 characters.",
            "Tags": ["Tag1", "Tag2", "Tag3"]
        }}
        ###
        JSON Output:
        """,
            },
        ],
        5: [
            # {
            #             "role": "system",
            #             "content": "You are an SEO expert. Analyze the given context from a website for Linux and open-source security professionals to create meta tags, meta keywords, and a concise meta description for SEO purposes. Provide structured JSON output with the top 5 to 8 Meta keywords, meta tags, and the Meta description. The Meta description should be up to 20 words long. Ensure the Meta keywords are distinct, surrounded by quotes, and relevant to the given context."
            # },
            {
                "role": "user",
                "content": f"""
        Instructions:
        1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
        2. Extract 5 to 10 high-volume Meta keywords and meta tags from the given context.
        3. Create a concise Meta description that summarizes the given context, ensuring that the Meta description's word length does not exceed 20 words.
        4. If the Meta description's word length exceeds 20 words, trim it to meet the limit.
        5. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
        6. The Meta keywords, meta tags, and Meta description must be strictly derived from the provided context, aligning with SEO best practices.
        7. Ensure that each Meta keyword is distinct from the others.
        8. Extract Meta tags that reflect key concepts and terms from the text, focused on infosecurity and Linux server management.
        9. Ensure these tags are specific, with each tag being a single impactful word or multiple authoritative words.
        10. List these tags in a format within brackets and separated by commas.
        11. Tags should be unique, relevant, and derived strictly from the content provided.
        12. Meta keywords and Tags must be unique from each other or similar but not exactly the same.
        13. Avoid words common to all content related to Linux and open source, including "linux" and "open source" and "cybersecurity".
        14. Results must be suitable for a Linux and info security professional audience who are generally highly-educated and experienced Linux sysadmins.
        15. The collection of meta tags should strictly relate to the context.
        16. Strictly adhere to SEO best practices in generating accurate Meta data for websites.
        17. Tags should be chosen for their low keyword difficulty and high search volume, relevant for boosting search engine visibility.
        18. Create primary single-word tags that are central to the themes of Linux, open source, infosecurity, and Linux server management.
        19. Keywords and tags must not be the same.

        Difference between "keywords" and "tags":
        - Keywords: high-level words or phrases that capture the primary topics and themes of the content.
        - Tags: low-level general labels that categorize the content into specific themes. These help with site navigation and categorizing content. Tags provide details that the keywords don’t convey, so it’s handy to use them together. 

        After creating tags and keywords for this context, review above instructions again to ensure you have not used words like "linux" and "open source" and "cybersecurity" in your results.

        ###
        Given Context: {context}
        ###
        Example Output:
        {{
            "Meta keywords": ["Keyword1", "Keyword2", "Keyword3"],
            "Meta description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 160 characters.",
            "Tags": ["Tag1", "Tag2", "Tag3"]
        }}
        ###
        JSON Output:
        """,
            }
        ],
        6: [
            {
                "role": "user",
                "content": f""" 
Please reset any previous configuration or instructions. We are starting over. No previous information on instructions should be considered. You are a helpful SEO consultant with knowledge of how SEO keywords and tags impact search results and how to identify them within a given context.  The requirement is to create keywords, meta tags, meta description, title tag and H1 tag for an article within the Linux and open source context for an infosec professional audience.  

Definitions:
Linux Security: Linux security refers to the set of practices and measures used to protect Linux-based operating systems from various security threats and vulnerabilities. Linux is a widely used open-source operating system that has gained popularity due to its security features, stability, and flexibility.

Tags: High-level words within the Linux security and open source context that is directly related to the provided content. Tags are formed based only on the specific topic being discussed in the provided content.

Meta Keywords: Meta keywords are specific meta tags located in the HTML head section of a webpage containing a list of keywords that represent the content of the page for search engines.

Title Tag: A title tag (or <title> tag) is an HTML element that provides a webpage title for search engines and internet browsers to use. It can appear in search engine results and link previews for the pages. 

H1 Tag: An H1 tag is the HTML used to create the main title on a webpage and helps indicate the page’s primary topic to visitors and search engines. It contains an opening <h1> tag, the title text, and a closing </h1> tag. 

Description: A summarized description of the article which tells regarding what the article is about and its main takeaways.

Please follow these instructions explicitly, step by step.
1.  Extract 3-5 meta keywords relevant to the context without using overly generic terms relevant to the article's context, focusing on high-volume terms.
2.  Create a list of 5-7 relevant high-volume tags based on the specified criteria within the given Linux security context, focusing on the specific topics of interest directly related to the content. Use "{title}" and "{h1_title}" to provide useful content as a basis for your Tag. Tags must not include phrases including "Linux security" or "open source" or "open source security" or "cybersecurity" or "network security" that would apply to any article within the Linux security context. Tags must be case-insensitive, singular form, and use natural English words without underscores or hyphens.
3.  Create a title tag under 60 characters or 7 words, following SEO practices. For "Advisory" content, use unique terms (e.g., SLE-15-SP4, CVE numbers, ELSA identifiers) from the article for distinction and ensure it's different from any H1 tag. If applicable, include the application name with its version (e.g., gdk-pixbuf2-2.42.6-4). Use "{title}" to reflect the content accurately and uniquely. Title tag must not be the same as "{h1_title}" or "{title}".
4.  Generate an H1 tag according to SEO best practices. Title and H1 tags must not be the same. H1 Tag can be no longer than 7 words or 70 characters. H1 Tag should be very descriptive and contain more detail about the article than title tags. H1 tags should be close to the main synopsis of the article. Use "{title}" to provide useful content as a basis for your H1 tag to make it unique. H1 tag must not be the same as "{h1_title}" or "{title}".
5.  Identify the type of article as one of Advisory, which is content related to a security update of some kind, or Feature, which is a piece of news or a story that digs deep on a particular topic.
6.  The description should be generated so that it highlights main points of the article and it should not be longer than 130 characters. It should be unique and should not match with other descriptions generated before.

###
Given Content: {context}
###
Example Output:
{{
    "Keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "Description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 150 characters.",
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
        7: [
            {
                "role": "user",
                "content": f""" 
As an SEO consultant for Linux security content, generate the following elements strictly adhering to the specified limits:

1. Keywords: 3-5 relevant, high-volume meta keywords. Exclude generic terms.

2. Tags: 5-7 specific, high-volume tags. Use singular, natural English words. No hyphens, underscores, or generic phrases like "Linux security" or "open source."

3. Title Tag: STRICTLY UNDER 50 CHARACTERS or 5 words. For advisories, include unique identifiers (e.g., CVE numbers). Must differ from H1.

4. H1 Tag: STRICTLY MAX 50 CHARACTERS or 5 words. More descriptive than title, summarizing main points. Must differ from title.

5. Type: "Advisory" (security update) or "Feature" (in-depth article).

6. Description: STRICTLY MAX 100 CHARACTERS or 10 words at max. Highlight main points concisely. Ensure uniqueness.

Use provided "{title}" and "{h1_title}" as reference for uniqueness.

Double-check all character and word counts before finalizing. Everything should fall under the conditions specified above else there 
will be punishment of wrong results. Before outputting results recheck whether the results are in the accurate length range or not.

###
Given Content: {context}
###
Example Output:
{{
    "Keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "Tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
    "Title": "Concise Title Tag (max 50 chars)",
    "H1": "Descriptive H1 Tag (max 50 chars)",
    "Type": "Advisory or Feature",
    "Description": "Brief, unique description (max 100 chars)."
}}
###
JSON Output:
"""
            }
        ],
    }

    return prompts[key]



def get_model():
    get_gpt_model = config.get("chatgpt", "gpt_model")
    model = int(get_gpt_model[0]) if get_gpt_model else 1
    gpt_model = {
        1: "gpt-3.5-turbo-1106",
        2: "gpt-4",
        3: "gpt-3.5-turbo",
        4: "gpt-4o mini",
        5: "gpt-4-turbo",
        6: "o1-preview",
        7: "gpt-4o"
    }
    return gpt_model.get(model, "gpt-3.5-turbo-1106")



def get_prompt(context, h1_title:str="", metadesc:str="", title:str=""):
    get_prompt_key = config.get("chatgpt", "prompt_key")
    prompt_key = int(get_prompt_key) if get_prompt_key else 1
    try:
        # dave print("Prompt key used  : ", prompt_key)
        prompt = promts_dict(prompt_key, context, h1_title, metadesc, title)
        return prompt
    except Exception as e:
        print(e)

