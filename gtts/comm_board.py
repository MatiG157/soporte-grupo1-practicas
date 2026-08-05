from kivy.app import App
from kivy.clock import mainthread
from kivy.factory import Factory
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout

from tts_client import speak

Builder.load_file('comm_board.kv')

# Categorías: cada frase es (icono_emoji, texto_a_decir)
CATEGORIES = {
    'Necesidades': [
        ('Necesito ir al baño'),
        ('Tengo sed'),
        ('Tengo hambre'),
        ('Estoy cansado'),
        ('Me duele algo'),
        ('Necesito ayuda'),
    ],
    'Emociones': [
        ('Estoy contento'),
        ('Estoy triste'),
        ('Estoy enojado'),
        ('Tengo miedo'),
        ('Estoy tranquilo'),
        ('Estoy confundido'),
    ],
    'Saludos': [
        ('Hola'),
        ('Chau, hasta luego'),
        ('Por favor'),
        ('Gracias'),
        ('¿Cómo estás?'),
        ('Sí'),
    ],
    'Respuestas': [
        ('Sí'),
        ('No'),
        ('No sé'),
        ('Esperá un momento'),
        ('¿Podés repetir?'),
        ('Basta, para'),
    ],
}


class CommBoard(BoxLayout):
    def on_kv_post(self, base_widget):
        # Crea los botones de categoría y muestra la primera por defecto
        first = True
        for name in CATEGORIES:
            btn = Factory.CategoryButton(text=name, state='down' if first else 'normal')
            btn.bind(on_press=lambda b, n=name: self.show_category(n))
            self.ids.category_row.add_widget(btn)
            first = False

        self.show_category(next(iter(CATEGORIES)))

    def show_category(self, name):
        grid = self.ids.buttons_grid
        grid.clear_widgets()
        for phrase in CATEGORIES[name]:
            btn = Factory.PhraseButton(text=f'{phrase}')
            btn.bind(on_press=lambda b, p=phrase: self.say_phrase(p))
            grid.add_widget(btn)

    def say_custom(self):
        text = self.ids.custom_text.text.strip()
        if text:
            self.say_phrase(text)
            self.ids.custom_text.text = ''

    def say_phrase(self, text):
        for child in self.ids.buttons_grid.children:
            child.disabled = True

        @mainthread
        def show_error(message):
            for child in self.ids.buttons_grid.children:
                child.disabled = False
            popup = Factory.Popup(
                title='Error',
                content=Factory.Label(text=message),
                size_hint=(0.7, 0.4),
            )
            popup.open()

        @mainthread
        def re_enable():
            for child in self.ids.buttons_grid.children:
                child.disabled = False

        speak(text, on_error=show_error, on_end=re_enable)


class CommBoardApp(App):
    def build(self):
        return CommBoard()


if __name__ == '__main__':
    CommBoardApp().run()
