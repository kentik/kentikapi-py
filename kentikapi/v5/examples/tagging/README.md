Example: HyperTagging Populator Batch
=====================================

In this example, we're creating 7 populators for the custom dimension `c_my_column`, replacing
all existing populators (because of the `True` parameter passed into the `Batch` constructor).


Running the example
-------------------

__Set options:__

Modify populator_batch.py, setting:

- `option_api_email`
- `option_api_token`
- `option_custom_dimension`


__Setup environment:__
  
    virtualenv venv
    source ./venv/bin/activate
    pip install -r requirements.txt


__Run:__

    python populator_batch.py


Deleting all populators
-----------------------

__Set options:__

Modify delete_all_populators.py, setting:

- `option_api_email`
- `option_api_token`
- `option_custom_dimension`


__Setup environment:__

Same as above, or do nothing if you're still in your virtual environment.


__Run:__

    python delete_all_populators.py


Exit virtal environment
-----------------------

If you're still in your virtual environment, exit with:

    deactivate
