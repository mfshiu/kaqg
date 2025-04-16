class ScqFeatures:
    level_descriptions_v1 = [
        ["Generate a short stem that is concise and straightforward, without excessive wording, clear and simple.",
         "Generate a medium-length stem that is neither too long nor too short, ensuring it adequately expresses the problem.",
         "Provide a detailed stem with rich content, challenging the learner's comprehension, ensuring clarity and no compromises."],

        ["The stem should contain very few technical terms, ensuring it is easy to understand and not overly complex or difficult.",
         "The stem should include a moderate number of technical terms, which should help express the problem without making it too difficult for the learner.",
         "The stem should use a high density of technical terms, challenging the learner and prompting deeper thinking."],

        ["Design the stem to test basic recall of facts or concepts only, requiring learners to remember fundamental information.",
         "The stem should go beyond simple recall, challenging the learner's ability to understand and synthesize knowledge.",
         "The stem should reflect higher-order thinking levels, especially analysis, creation, or evaluation. The question should stimulate deep thinking and encourage learners to make complex decisions."],

        ["The option text should be short, concise, and impactful, avoiding unnecessary length or distractions.",
         "The option text should be moderate, neither too simple nor too long, providing a certain level of challenge.",
         "The option text should be sufficiently elaborate and challenging, avoiding overly simple or very brief options."],

        ["Ensure very low similarity between the options, each option should be clearly distinguishable and not easily confused.",
         "Ensure moderate similarity between the options, with some shared elements, but still clearly distinguishable.",
         "Ensure very high similarity between the options, making them appear very similar, but differing in subtle details."],

        ["Ensure high relevance between the stem and the options, with the options closely tied to the stem's content, almost undeniable.",
         "The stem and options should maintain moderate relevance, with some connection, but not too obvious.",
         "The relevance between the stem and the options should be very low, with the options only loosely related to the stem, avoiding direct connections."],

        ["The options should contain one highly plausible but incorrect choice, designed to mislead learners who do not fully understand the concept.",
         "The options should contain two very plausible but incorrect answers, designed to challenge learners by appearing correct at first glance.",
         "Include multiple highly attractive distractors, which should seem very plausible and likely to mislead learners with incomplete understanding of the concept."]
    ]

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
