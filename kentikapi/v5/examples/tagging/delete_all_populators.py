from kentikapi.v5 import tagging

#
# Example: Delete all populators for a HyperScale custom dimension
#
# This creates an empty batch of populators for a HyperScale custom dimension,
# replacing everything that's already there with... nothing, since we don't define
# any populators in the batch.
#

# ---------------------------------------------------
# Change these options:
option_api_email = 'me@email.com'
option_api_token = '673244805e76d01d01e42d32c56d64c2'
option_custom_dimension = 'c_my_column'
# ---------------------------------------------------


# -----
# initialize a batch that will replace all populators
# -----
batch = tagging.Batch(True)

# no populators entered, so everything just gets deleted

# -----
# Showtime! Submit the batch as populators for the configured custom dimension
# -----
client = tagging.Client(option_api_email, option_api_token)
client.submit_populator_batch(option_custom_dimension, batch)
