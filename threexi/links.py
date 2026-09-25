"""Export working client URLs from normalized users without editing the database."""
import json
from urllib.parse import urlencode, quote
from .core import ConfigError, hostname, public_address, read_db


def export_links(path, sni, authority='', address=''):
    sni = hostname(sni)
    authority = hostname(authority or sni)
    address = public_address(address or sni)
    endpoint = '['+address+']' if ':' in address else address
    db = read_db(path)
    try:
        rows = [(row,json.loads(row['stream_settings'])) for row in db.execute("SELECT * FROM inbounds WHERE enable=1 AND protocol='vless' AND (node_id IS NULL OR node_id=0)")]
        rows = [(row,stream) for row,stream in rows if stream.get('network') == 'grpc']
        if len(rows) != 1:
            raise ConfigError('Exactly one enabled local VLESS gRPC inbound is required.')
        inbound,stream = rows[0]
        grpc = stream.get('grpcSettings',{})
        params = dict(encryption='none', security='tls', sni=sni, fp='chrome', alpn='h2',
                      type='grpc', authority=authority, serviceName=grpc['serviceName'],
                      mode='multi' if grpc.get('multiMode') else 'gun')
        result=[]
        for client in db.execute('SELECT c.uuid,c.email FROM clients c JOIN client_inbounds ci ON c.id=ci.client_id WHERE ci.inbound_id=? AND c.enable=1 ORDER BY c.id',(inbound['id'],)):
            result.append('vless://'+client['uuid']+'@'+endpoint+':443?'+urlencode(params)+'#'+quote('3xi-'+client['email'],safe=''))
        return result
    finally:
        db.close()
