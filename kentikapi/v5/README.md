Kentik Python API
=================

HyperTagging API
----------------

Kentik HyperTagging API allows asynchronous processing of large batches of tags and custom dimensions. 
A batch contains either tags or populators for a single custom dimension. A populator or tag is represented
by a `value`, and a `Criteria` object. The rest of this document will discuss custom dimension populators,
but also applies to tags when a tag batch is submitted.


### Using the Kentik HyperTagging batch API

Declare the source of the Kentik API module in your `requirements.txt`:

    git+https://github.com/kentik/api-client#egg=kentikapi

Create a virtual environment, and fetch the Kentik API module:

    virtualenv venv
    pip install -r requirements.txt

In your Python code, import the tagging classes of the API module:

    from kentikapi.v5 import tagging


### Initializing a batch

The batch constructor takes a single parameter: a boolean that signals whether the batch processor should
delete any populators for this custom dimension that are not explicitly mentioned in the batch:

    # this batch will delete all populators for this custom dimension that aren't explicitly mentioned
    batch = tagging.Batch(True)

    # this batch will only upsert and delete as instructed, but do nothing with populators not mentioned
    batch = tagging.Batch(False)


### Defining criteria for a populator

A populator is defined by a value and a `Criteria` object. Its constructor takes a single argument, the
flow direction that this criteria matches, either `src`, `dst`, or `either`.

    crit = tagging.Criteria('src')  # 'src', 'dst', or 'either'

Add conditions to the criteria with the following methods:

- `add_asn(asn<int>)`
- `add_asn_range(start<int>, end<int>)`
- `add_bgp_as_path(bgp_as_path<string>)`
- `add_bgp_community(bgp_community<string>)`
- `add_country_code(country_code<string>)`
- `add_device_name(device_name<string>)`
- `add_device_type(device_type<string>)`
- `add_interface_name(interface_name<string>)`
- `add_ip_address(ip_address<string>)`
- `add_last_hop_asn_name(last_hop_asn_name<string>)`
- `add_mac_address(mac_address<string>)`
- `add_next_hop_asn(next_hop_asn<int>)`
- `add_next_hop_asn_name(next_hop_asn_name<string>)`
- `add_next_hop_asn_range(start<int>, end<int>)`
- `add_next_hop_ip_address(next_hop_ip_address<string>)`
- `add_port(port_num<int>)`
- `add_port_range(start<int>, end<int>)`
- `add_protocol(protocol<int>)`
- `add_site_name(site_name<string>)`
- `add_tcp_flag(tcp_flag<int>)`, where `tcp_flag` in [1, 2, 4, 8, 16, 32, 64, 128]
- `set_tcp_flags(tcp_flag<int>)`

Add the criteria to the batch. The batch processor will decide if this is an insert or upsert. You can have multiple
criteria per value, and all existing populators for this value will be replaced with what's in the batch. 

    batch.add_upsert('column_value', crit)    # (set the appropriate value for this populator)


### Deleting populator values

If the batch was defined with `False` passed into the constructor, you can still delete specific populator values.
These deletes occur before the upserts, and since the upserts replace all existing populators for the specified values,
there's no need to list values here that are also listed in upserts - they'd be ignored anyway:

    batch.add_delete('column_value')   # (set the appropriate value for the populator(s) being deleted)


### Submit the batch

Initialize a HyperTag API client, and submit the batch:

    client = tagging.Client('my@email.com', 'dbb87934ae73198ce0c62d32f7f767de')   # (set your credentials)

    # if this is a populator batch:
    client.submit_populator_batch('custom_dimension_name', batch)        # (set the custom dimension name)

    # if this is a tag batch:
    client.submit_tag_batch(batch)

