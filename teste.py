from kokoro import KPipeline
import numpy as np
import soundfile as sf

lang_code = 'p'

pipeline = KPipeline(lang_code=lang_code) 

text = """Ola, eu sou a mica, sua agente IA personalizada para windows.
estou aqui para te ajudar no que for nescessario no dia a dia, melhorando 
sua performace e usabilidade do sistema."""

generator = pipeline(text=text, voice='pf_dora')

audio_chunck =[]

for _,_, audio in generator:
    audio_chunck.append(audio)

audio_completo = np.concatenate(audio_chunck)
sf.write('audio.wav', audio_completo,24000)