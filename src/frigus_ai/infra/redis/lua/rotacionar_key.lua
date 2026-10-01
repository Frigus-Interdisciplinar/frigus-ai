-- Troca a key do usuário de uma vez: apaga o lookup da antiga (se houver) e grava user_key + lookup
-- novos. ARGV[4] é o prefixo das chaves de lookup (o hash antigo só é conhecido dentro do script).
local antigo = redis.call('GET', KEYS[1])
if antigo then redis.call('DEL', ARGV[4] .. antigo) end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
return 1
