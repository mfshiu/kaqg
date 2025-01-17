def get_agent_config(toml_data):
    broker_name = toml_data['broker']['broker_name']

    agent_config = {
        'version': toml_data['system']['version'],
        'broker': {
            **toml_data['broker'].get(broker_name, {})
        }
    }

    return agent_config


# def get_agent_config(toml_data):
#     # Identify the broker type specified in the configuration
#     broker_type = toml_data['broker']['broker_type']

#     # Retrieve all attributes for the specified broker type
#     agent_config = {
#         'version': toml_data['system']['version'],
#         'broker': {
#             'broker_type': broker_type,
#             **toml_data['broker'].get(broker_type, {})
#         }
#     }

#     return agent_config
