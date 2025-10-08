 C:\Users\Usuario\Desktop\projetoblz-master> python -c "
>> print('🔍 Iniciando debug...')
>> try:
>>     from app import app, db
>>     print('✅ Módulos importados')
>>
>>     with app.app_context():
>>         print('✅ Contexto da app OK')
>>
>>     print('🚀 Iniciando servidor...')
>>     app.run(debug=True, port=5000)
>>
>> except Exception as e:
>>     print(f'❌ ERRO: {e}')
>>     import traceback
>>     traceback.print_exc()
>>     input('Pressione Enter para sair...')
