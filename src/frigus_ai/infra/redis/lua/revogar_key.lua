-- ARGV[1] é o prefixo das chaves de lookup. Retorna 0 se o usuário não tinha key ativa.
local antigo = redis.call('GET', KEYS[1])
if not antigo then return 0 end
redis.call('DEL', KEYS[1], ARGV[1] .. antigo)
return 1
