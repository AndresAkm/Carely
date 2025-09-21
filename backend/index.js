import exp from 'express'
import dotenv from 'dotenv'
dotenv.config()

const app = exp()
const PORT = process.env.PORT || 3012

app.listen(PORT, () => { 
    console.log(`Puerto ${PORT} escuchando el servidor`)
    console.log(`Web disponible en http://localhost:${PORT}`) }) 
     
app.get('/', (req, res) => { res.send('Hola, esto funciona') })