class ScqFeatures:
    level_descriptions = [
        ["Generate a short stem containing 5 to 15 words, no more, no less.", 
         "Generate a medium stem containing 16 to 30 words, no more, no less.", 
         "Provide a long stem that exceeds 30 words in length. Make sure it is not shorter."],
        ["The stem should contain between 0 and 2 technical terms. Do not exceed this limit.", 
         "The stem should contain between 2 and 4 technical terms. Do not exceed this limit.", 
         "Use a high density of technical language in the stem, with more than 3 technical terms included."],
        ["Design the stem at the remembering level — it should test basic recall of facts or concepts only.", 
         "The stem should target the understanding and synthesizing levels of Bloom’s Taxonomy. It should go beyond recall to assess comprehension and integration of knowledge.", 
         "The stem should reflect Bloom’s higher-order levels — specifically analyzing, creating, or evaluating. It should encourage deep thinking and decision-making based on complex information."],
        ["The option text should be no longer than 4 words. Strictly follow this range.", 
         "The option text should be no shorter than 3 words and no longer than 6 words. Stay strictly within this range.", 
         "The option text must be at least 5 words long. Avoid short or very brief options."],
        ["Ensure low similarity between options — they should be less than 20% similar in wording or structure. Each option must be clearly distinct from the others.", 
         "Ensure the options have moderate similarity, with approximately 50% overlap in wording or structure. They should share some elements but still be distinguishable.", 
         "Ensure high similarity between options, with more than 80% overlap in wording or structure. Options should appear very similar but differ in subtle ways."],
        ["Ensure high relevance between the stem and the options, with over 80% semantic or contextual overlap. The options should be closely tied to the stem's content.", 
         "Ensure moderate relevance between the stem and the options, with approximately 50% semantic or contextual overlap. The options should be related, but not too obvious.", 
         "Ensure low relevance between the stem and the options — the semantic or contextual connection should be below 20%. The options should appear only loosely related to the stem."],
        ["The options should contain one highly plausible but incorrect choice designed to mislead learners who lack full understanding of the concept.", 
         "The options should contain two very plausible but incorrect answers, designed to challenge learners by appearing correct at first glance.", 
         "Include more than 3 highly attractive distractors — these should be incorrect options that seem very plausible and are likely to mislead learners with incomplete understanding."]
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
