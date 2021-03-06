import logging, json, time
from Crypt import CryptBitcoin
from Plugin import PluginManager

@PluginManager.acceptPlugins
class User(object):
	def __init__(self, master_address=None, master_seed=None, data={}):
		if master_seed:
			self.master_seed = master_seed
			self.master_address = CryptBitcoin.privatekeyToAddress(self.master_seed)
		elif master_address:
			self.master_address = master_address
			self.master_seed = data.get("master_seed")
		else:
			self.master_seed = CryptBitcoin.newSeed()
			self.master_address = CryptBitcoin.privatekeyToAddress(self.master_seed)
		self.sites = data.get("sites", {})
		self.certs = data.get("certs", {})

		self.log = logging.getLogger("User:%s" % self.master_address)


	# Save to data/users.json
	def save(self):
		users = json.load(open("data/users.json"))
		if not self.master_address in users: users[self.master_address] = {} # Create if not exits
		user_data = users[self.master_address]
		if self.master_seed: user_data["master_seed"] = self.master_seed
		user_data["sites"] = self.sites
		user_data["certs"] = self.certs
		open("data/users.json", "w").write(json.dumps(users, indent=2, sort_keys=True))
		self.log.debug("Saved")


	# Get user site data
	# Return: {"auth_address": "xxx", "auth_privatekey": "xxx"}
	def getSiteData(self, address, create=True):
		if not address in self.sites: # Genreate new BIP32 child key based on site address
			if not create: return {"auth_address": None, "auth_privatekey": None} # Dont create user yet
			s = time.time()
			address_id = int(address.encode("hex"), 16) # Convert site address to int
			auth_privatekey = CryptBitcoin.hdPrivatekey(self.master_seed, address_id)
			self.sites[address] = {
				"auth_address": CryptBitcoin.privatekeyToAddress(auth_privatekey),
				"auth_privatekey": auth_privatekey
			}
			self.save()
			self.log.debug("Added new site: %s in %.3fs" % (address, time.time()-s))
		return self.sites[address]


	# Get BIP32 address from site address
	# Return: BIP32 auth address
	def getAuthAddress(self, address, create=True):
		cert = self.getCert(address)
		if cert:
			return cert["auth_address"]
		else:
			return self.getSiteData(address, create)["auth_address"]


	def getAuthPrivatekey(self, address, create=True):
		cert = self.getCert(address)
		if cert:
			return cert["auth_privatekey"]
		else:
			return self.getSiteData(address, create)["auth_privatekey"]


	# Add cert for the user
	def addCert(self, auth_address, domain, auth_type, auth_user_name, cert_sign):
		domain = domain.lower()
		auth_privatekey = [site["auth_privatekey"] for site in self.sites.values() if site["auth_address"]  == auth_address][0] # Find privatekey by auth address
		cert_node = {
			"auth_address": auth_address,
			"auth_privatekey": auth_privatekey,
			"auth_type": auth_type,
			"auth_user_name": auth_user_name,
			"cert_sign": cert_sign
		}
		# Check if we have already cert for that domain and its not the same
		if self.certs.get(domain) and self.certs[domain] != cert_node: 
			raise Exception("You already have certificate for this domain: %s/%s@%s" % (self.certs[domain]["auth_type"], self.certs[domain]["auth_user_name"], domain))
		elif self.certs.get(domain) == cert_node: # Same, not updated
			return None
		else: # Not exits yet, add
			self.certs[domain] = cert_node
			self.save()
			return True


	def setCert(self, address, domain):
		site_data = self.getSiteData(address)
		if domain:
			site_data["cert"] = domain
		else:
			del site_data["cert"]
		self.save()
		return site_data


	# Get cert for the site address
	# Return: { "auth_address": ..., "auth_privatekey":..., "auth_type": "web", "auth_user_name": "nofish", "cert_sign": ... } or None
	def getCert(self, address):
		site_data = self.getSiteData(address, create=False)
		if not site_data or not "cert" in site_data: return None # Site dont have cert
		return self.certs.get(site_data["cert"])


	# Get cert user name for the site address
	# Return: user@certprovider.bit or None
	def getCertUserId(self, address):
		site_data = self.getSiteData(address, create=False)
		if not site_data or not "cert" in site_data: return None # Site dont have cert
		cert = self.certs.get(site_data["cert"])
		if cert:
			return cert["auth_user_name"]+"@"+site_data["cert"]