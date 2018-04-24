import json
import requests
from sets import Set

#
# HyperScale Tagging API client
#

_allowedValueChars = Set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
_allowedCustomDimensionChars = _allowedValueChars

# ----------------------------------------
# Batch collects tags or populators as values and criteria.
class Batch:
    def __init__(self, replace_all):
        self.replace_all = replace_all
        self.upserts = dict()
        self.upserts_size = dict()   # keep track of json str size per value
        self.deletes = set()

    def _validate_value(self, value):
        if not Set(value).issubset(_allowedValueChars):
            raise ValueError('Invalid value "%s": must only contain letters, digits, underscores, and dashes' % value)
        if len(value) < 2 or len(value) > 20:
            raise ValueError('Invalid value "%s": must be between 2-20 characters' % value)

    # add a tag or populator to the batch by value and criteria
    def add_upsert(self, value, criteria):
        self._validate_value(value)

        v = value.lower()
        criteria_array = self.upserts.get(v)
        if criteria_array == None:
            criteria_array = []
            # start with # '{"value": "some_value", "criteria": []}, '
            self.upserts_size[v] = 31 + len(value)
        criteria_array.append(criteria.to_dict())
        self.upserts[v] = criteria_array
        self.upserts_size[v] += criteria.json_size()


    # delete a tag or populator by value - these are processed before upserts
    def add_delete(self, value):
        self._validate_value(value)

        v = value.strip().lower()
        if len(v) == 0:
            raise ValueError("Invalid value for delete. Value is empty.")

        self.deletes.add(v)

    # return an array of batch parts to submit
    def parts(self):
        parts = []

        upserts = dict()
        deletes = []

        # we keep track of the batch size as we go (pretty close approximation!) so we can chunk it small enough
        # to limit the HTTP posts to under 3.5MB
        max_upload_size = 3500000

        # loop upserts first - fit the deletes in afterward
        base_part_size = 118 # '{"replace_all": true, "complete": false, "guid": "6659fbfc-3f08-42ee-998c-9109f650f4b7", "upserts": [], "deletes": []}'
        if not self.replace_all:
            base_part_size += 1 # yeah, this is totally overkill :)

        part_size = base_part_size
        for value in self.upserts:
            if (part_size + self.upserts_size[value]) >= max_upload_size:
                # this record would put us over the limit - close out the batch part and start a new one
                print "Finished batch: %d" % part_size
                parts.append(BatchPart(self.replace_all, upserts, deletes))
                upserts = dict()
                deletes = []
                part_size = base_part_size

            upserts[value] = self.upserts[value]
            part_size += self.upserts_size[value]    # updating the approximate size of the batch

        for value in self.deletes:
            # delete adds length of string plus quotes, comma and space
            if (part_size + len(value) + 4) >= max_upload_size:
                parts.append(BatchPart(self.replace_all, upserts, deletes))
                upserts = dict()
                deletes = []
                part_size = base_part_size

            deletes.append({ 'value': value })
            part_size += len(value) + 4

        if len(upserts) + len(deletes) > 0:
            # finish the batch
            parts.append(BatchPart(self.replace_all, upserts, deletes))

        if len(parts) == 0:
            if self.replace_all == False:
                raise ValueError("Batch has no data, and 'replace_all' is False")
            parts.append(BatchPart(self.replace_all, dict(), []))

        # last part finishes the batch
        parts[-1].set_last_part()
        return parts


# ----------------------------------------
# BatchPart contains tags/populators to be sent as part of a (potentially) multi-part logical batch
class BatchPart:
    def __init__(self, replace_all, upserts, deletes):
        if replace_all not in [True, False]:
            raise ValueError("Invalid value for replace_all. Must be True or False.")

        self.replace_all = replace_all
        self.complete = False
        self.upserts = upserts
        self.deletes = deletes


    # marks this part as the last to be sent for a logical batch
    def set_last_part(self):
        self.complete = True


    # build JSON with the input guid
    def build_json(self, guid):
        upserts = []
        for value in self.upserts:
            upserts.append({ "value": value, "criteria": self.upserts[value] })
        return json.dumps({'replace_all': self.replace_all, 'guid': guid, 'complete': self.complete, 'upserts': upserts, 'deletes': self.deletes})


# ----------------------------------------
# Criteria defines a set of rules that must match for a tag or populator.
# A flow record is tagged with this value if it matches at least one value from each non-empty criteria.
class Criteria:
    def __init__(self, direction):
        # try to approximate the string size as we add to the criteria - starts with curly brackets, comma, space, length of direction
        self._size = len(direction) + 20 # from '{"direction": "", } '
        self._json_dict = dict()

        v = direction.lower()
        if v not in ["src", "dst", "either"]:
            raise ValueError("Invalid value for direction. Valid: src, dst, either.")
        self._json_dict['direction'] = v
        self._has_field = False


    def to_dict(self):
        return self._json_dict

    def json_size(self):
        """
        Return the approximate size of this criteria represented as JSON
        """
        return self._size


    def _ensure_field(self, key):
        """ ensure a non-array field """
        if self._has_field:
            self._size += 2  # comma, space
        self._has_field = True

        self._size += len(key) + 4  # 2 quotes, colon, space


    def _ensure_array(self, key, value):
        """ ensure an array field """
        if key not in self._json_dict:
            self._json_dict[key] = []

            self._size += 2             # brackets
            self._ensure_field(key)

        if len(self._json_dict[key]) > 0:
            # this array already has an entry, so add comma and space
            self._size += 2

        if type(value) is str:
            self._size += 2  # quotes
        self._size += len(str(value))

        self._json_dict[key].append(value)


    def add_port(self, port):
        if port < 0 or port > 65535:
            raise ValueError("Invalid port. Valid: 0-65535.")
        self._ensure_array('ports', str(port))


    def add_port_range(self, start, end):
        if start < 0 or start > 65535:
            raise ValueError("Invalid start port. Valid: 0-65535.")
        if end < 0 or end > 65535:
            raise ValueError("Invalid end port. Valid: 0-65535.")

        if start == end:
            self.add_port(start)
            return

        ports_str = "%d-%d" % (start, end)
        self._ensure_array('ports', ports_str)


    def add_vlan(self, vlan):
        if vlan < 0 or vlan > 4095:
            raise ValueError("Invalid vlan. Valid: 0-4095.")
        self._ensure_array('vlans', str(vlan))


    def add_vlan_range(self, start, end):
        if start < 0 or start > 4095:
            raise ValueError("Invalid start vlan. Valid: 0-4095.")
        if end < 0 or end > 4095:
            raise ValueError("Invalid end vlan. Valid: 0-4095.")

        if start == end:
            self.add_vlan(start)
            return

        self._ensure_array('vlans', '%d-%d' % (start, end))


    def add_protocol(self, protocol):
        if protocol < 0 or protocol > 255:
            raise ValueError("Invalid protocol. Valid: 0-255.")

        self._ensure_array('protocols', protocol)


    def add_asn(self, asn):
        _validate_asn(asn)
        self._ensure_array('asns', str(asn))


    def add_asn_range(self, start, end):
        _validate_asn(start)
        _validate_asn(end)

        if start > end:
            raise ValueError("Invalid ASN range. Start must be before end.")

        if start == end:
            self.add_asn(start)
            return

        self._ensure_array('asns', '%d-%d' % (start, end))


    def add_last_hop_asn_name(self, last_hop_asn_name):
        v = last_hop_asn_name.strip()
        if len(v) == 0:
            raise ValueError("Invalid last_hop_asn_name. Value is empty.")

        self._ensure_array('last_hop_asn_names', v)


    def add_next_hop_asn(self, next_hop_asn):
        _validate_asn(next_hop_asn)
        self._ensure_array('next_hop_asns', str(next_hop_asn))


    def add_next_hop_asn_range(self, start, end):
        if start == end:
            self.add_next_hop_asn(start)
            return

        _validate_asn(start)
        _validate_asn(end)
        self._ensure_array('next_hop_asns', '%d-%d' % (start, end))


    def add_next_hop_asn_name(self, next_hop_asn_name):
        v = next_hop_asn_name.strip()
        if len(v) == 0:
            raise ValueError("Invalid next_hop_asn_name. Value is empty.")

        self._ensure_array('next_hop_asn_names', v)


    def add_bgp_as_path(self, bgp_as_path):
        v = bgp_as_path.strip()
        if len(v) == 0:
            raise ValueError("Invalid bgp_as_path. Value is empty.")

        # TODO: validate
        self._ensure_array('bgp_as_paths', v)


    def add_bgp_community(self, bgp_community):
        v = bgp_community.strip()
        if len(v) == 0:
            raise ValueError("Invalid bgp_community. Value is empty.")

        # TODO: validate
        self._ensure_array('bgp_communities', v)


    # add a single TCP flag - will be OR'd into the existing bitmask
    def add_tcp_flag(self, tcp_flag):
        if tcp_flag not in [1, 2, 4, 8, 16, 32, 64, 128]:
            raise ValueError("Invalid TCP flag. Valid: [1, 2, 4, 8, 16,32, 64, 128]")

        prev_size = 0

        if self._json_dict.get('tcp_flags') == None:
            self._json_dict['tcp_flags'] = 0
        else:
            prev_size = len(str(self._json_dict['tcp_flags'])) + len('tcp_flags') + 3  # str, key, key quotes, colon
        self._json_dict['tcp_flags'] |= tcp_flag

        # update size
        new_size = len(str(self._json_dict['tcp_flags'])) + len('tcp_flags') + 3  # str, key, key quotes, colon
        self._size += new_size - prev_size

        if prev_size == 0 and self._has_field:
            # add the comma and space
            self._size += 2
        self._has_field = True


    # set the complete tcp flag bitmask
    def set_tcp_flags(self, tcp_flags):
        if tcp_flags < 0 or tcp_flags > 255:
            raise ValueError("Invalid tcp_flags. Valid: 0-255.")

        prev_size = 0
        if self._json_dict.get('tcp_flags') != None:
            prev_size = len(str(self._json_dict['tcp_flags'])) + len('tcp_flags') + 3  # str, key, key quotes, colon

        self._json_dict['tcp_flags'] = tcp_flags

        # update size
        new_size = len(str(self._json_dict['tcp_flags'])) + len('tcp_flags') + 3  # str, key, key quotes, colon
        self._size += new_size - prev_size

        if prev_size == 0 and self._has_field:
            # add the comma and space
            self._size += 2
        self._has_field = True


    def add_ip_address(self, ip_address):
        v = ip_address.strip()
        if len(v) == 0:
            raise ValueError("Invalid ip_address. Value is empty.")

        # TODO: validate?
        self._ensure_array('ip_addresses', v)


    def add_mac_address(self, mac_address):
        v = mac_address.strip()
        if len(v) == 0:
            raise ValueError("Invalid mac_address. Value is empty.")

        # TODO: validate?
        self._ensure_array('mac_addresses', v)


    def add_country_code(self, country_code):
        v = country_code.strip()
        if len(v) == 0:
            raise ValueError("Invalid country_code. Value is empty.")

        # TODO: validate?
        self._ensure_array('country_codes', v)


    def add_site_name(self, site_name):
        v = site_name.strip()
        if len(v) == 0:
            raise ValueError("Invalid site_name. Value is empty.")

        self._ensure_array('site_names', v)


    def add_device_type(self, device_type):
        v = device_type.strip()
        if len(v) == 0:
            raise ValueError("Invalid device_type. Value is empty.")

        self._ensure_array('device_types', v)


    def add_interface_name(self, interface_name):
        v = interface_name.strip()
        if len(v) == 0:
            raise ValueError("Invalid interface_name. Value is empty.")

        self._ensure_array('interface_names', v)


    def add_device_name(self, device_name):
        v = device_name.strip()
        if len(v) == 0:
            raise ValueError("Invalid device_name. Value is empty.")

        self._ensure_array('device_names', v)


    def add_next_hop_ip_address(self, next_hop_ip_address):
        v = next_hop_ip_address.strip()
        if v == 0:
            raise ValueError("Invalid next_hop_ip_address. Value is empty.")

        self._ensure_array('next_hop_ip_addresses', v)


def _validate_asn(asn):
    if asn < 0 or asn > 4294967295:
        raise ValueError("Invalid ASN. Valid: 0-4294967295")


# ----------------------------------------
# Tagging client submits HyperScale batches to Kentik
class Client:
    def __init__(self, api_email, api_token):
        self.api_email = api_email
        self.api_token = api_token


    def _submit_batch(self, url, batch):
        # TODO: validate column_name
        batch_parts = batch.parts()

        guid = ""
        headers = {
                'user-agent': 'kentik-python-api/0.1',
                'Content-Type': 'application/json',
                'X-CH-Auth-Email': self.api_email,
                'X-CH-Auth-API-Token': self.api_token
        }

        # submit each part
        for batch_part in batch_parts:
            # submit
            resp = requests.post(url, headers=headers, data=batch_part.build_json(guid))

            # print the HTTP response to help debug
            print resp.text

            # break out at first sign of trouble
            resp.raise_for_status()
            guid = resp.json()['guid']
            if guid == None or len(guid) == 0:
                raise RuntimeError('guid not found in batch response')


    # submit a populator batch
    def submit_populator_batch(self, column_name, batch):
        if not Set(column_name).issubset(_allowedCustomDimensionChars):
            raise ValueError('Invalid custom dimension name "%s": must only contain letters, digits, underscores, and dashes' % column_name)
        if len(column_name) < 3 or len(column_name) > 20:
            raise ValueError('Invalid value "%s": must be between 3-20 characters' % column_name)

        url = 'https://api.kentik.com/api/v5/batch/customdimensions/%s/populators' % column_name
        self._submit_batch(url, batch)


    # submit a tag batch
    def submit_tag_batch(self, batch):
        url = 'https://api.kentik.com/api/v5/batch/tags'
        self._submit_batch(url, batch)
