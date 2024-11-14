import toml
    
def get_agent_config():
    with open("./wastepro.toml", "r") as file:
        toml_data = toml.load(file)

    # Read the system version
    version = toml_data['system']['version']

    # Identify the broker type specified in the configuration
    broker_type = toml_data['broker']['broker_type']

    # Retrieve all attributes for the specified broker type
    agent_config = {
        'version': version,
        'broker': {
            'broker_type': broker_type,
            **toml_data['broker'].get(broker_type, {})
        }
    }

    return agent_config
