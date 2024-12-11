[
            {
                "role": "user",
                "content": f"""
Instructions:
1. Analyze the provided text to identify the most relevant Meta keywords for SEO optimization.
2. Extract 5 to 10 high-volume Meta keywords from the given context.
3. Extract 3 to 5 tags from the given context.
4. Create a concise Meta description that summarizes the given context, ensuring that the Meta description's word length does not exceed 20 words.
5. Meta description must contains few generated keywords as well to help in SEO.
6. If the Meta description's word length exceeds 20 words, trim it to meet the limit.
7. Format each Meta keyword in quotes and separate them with commas, ensuring no repetition and high relevance to the context.
8. The Meta keywords, tags, and Meta description must be strictly derived from the provided context, aligning with SEO best practices.
9. Ensure that each Meta keyword is distinct from the others.
10. Extract tags that reflect key concepts and terms from the text, focused on infosecurity and Linux server management.
11. Ensure these tags are broad and general, with each tag being a single impactful word.
12. List these tags in a format within brackets and separated by commas.
13. Tags should be unique, relevant, and derived strictly from the content provided.
14. Meta keywords and Tags must be unique from each other.
15. Avoid words common to all content related to Linux and open source, including "linux" and "open source" and "cybersecurity".
16. Results must be suitable for a Linux and info security professional audience who are generally highly-educated and experienced Linux sysadmins.
17. The collection of tags should strictly relate to the context.
18. Strictly adhere to SEO best practices in generating accurate Meta data for websites.
19. Tags should be chosen for their relevance to the broader themes and topics of the content.
20. Create primary single-word tags that are central to the themes of Linux, open source, infosecurity, and Linux server management.

Difference between "keywords" and "tags":
- Keywords: high-level words or phrases that capture the primary topics and themes of the content.
- Tags: broad, general labels that categorize the content into specific themes. These help with site navigation and categorizing content. Tags provide details that the keywords don’t convey, so it’s handy to use them together.

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