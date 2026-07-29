import kivy
from kivy.app import App

class calculadora(App):
    def actualizar_display(self, texto_boton):
    
        display = self.root.ids.display
    
        if display.text == "0" or display.text == "Error":
            display.text = ""
            
        display.text += texto_boton

    def limpiar_display(self):
        self.root.ids.display.text = "0"

    def calcular_resultado(self):
        display = self.root.ids.display
        try:
     
            resultado = str(eval(display.text))
            display.text = resultado
        except Exception:
      
            display.text = "Error"

if __name__ == '__main__':
    calculadora().run()