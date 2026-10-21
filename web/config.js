// Pegue aquí la configuración de la app web de Firebase:
// Consola de Firebase -> Configuración del proyecto -> General -> Tus apps -> (</>) -> Configuración.
// Estos valores NO son secretos: la seguridad la dan las reglas de Firestore.
// Mientras projectId esté vacío, la página usa datos de demostración.
export const firebaseConfig = {
  apiKey: 'AIzaSyAvL5XUArLR9TtDpc7uSRqsxXu4vF7klDs',
  authDomain: 'colmena-iot-tec.firebaseapp.com',
  projectId: 'colmena-iot-tec',
  storageBucket: 'colmena-iot-tec.firebasestorage.app',
  messagingSenderId: '146101711658',
  appId: '1:146101711658:web:8147ded48c2d64354e2453',
};

export const COLECCION = 'lecturas';

// Rango máximo permitido en días, para no gastar la cuota de lecturas.
export const MAX_DIAS_RANGO = 31;
