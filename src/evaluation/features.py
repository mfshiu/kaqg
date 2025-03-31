class ScqFeatures:
    level_descriptions = [
        ["Short stem length (10 to 25 characters)", 
         "Medium stem length (15 to 35 characters)", 
         "Long stem length (over 20 characters)"],
        ["Few or no technical terms in stem (0 to 2 terms)", 
         "Moderate number of technical terms in stem (2 to 4 terms)", 
         "Many technical terms in stem (more than 3 terms)"],
        ["Only requires memorization of knowledge points", 
         "Requires understanding and synthesis of knowledge points", 
         "Requires analysis, synthesis, or evaluation"],
        ["Short option text (1 to 5 characters)", 
         "Medium option text (3 to 8 characters)", 
         "Long option text (more than 5 characters)"],
        ["Low similarity between options (below 30%)", 
         "Moderate similarity between options (around 45%)", 
         "High similarity between options (above 60%)"],
        ["Low relevance between stem and options (below 30%)", 
         "Moderate relevance between stem and options (around 45%)", 
         "High relevance between stem and options (above 60%)"],
        ["Includes 1 highly attractive distractor", 
         "Includes 2 highly attractive distractors", 
         "Includes more than 3 highly attractive distractors"]
    ]

    keys = [
        "stem_length",
        "stem_technical_term_density",
        "stem_cognitive_level",
        "option_average_length",
        "option_similarity",
        "stem_option_similarity",
        "high_distractor_count"
    ]

    titles = [
        "Stem Length",
        "Technical Term Density in Stem",
        "Cognitive Level",
        "Average Option Length",
        "Option Similarity",
        "Stem-Option Similarity",
        "Number of High-Attraction Distractors"
    ]

    criteria = [
        {
            "key": k,
            "title": t,
            "levels": d
        }
        for k, t, d in zip(keys, titles, level_descriptions)
    ]
