-- Os dois SETs num script só: o Redis roda o script inteiro sem intercalar outros comandos, então
-- nunca sobra user_key sem lookup (key que "existe" mas não autentica). Retorna 0 se o NX falhou.
if redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3], 'NX') then
    redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
    return 1
end
return 0
