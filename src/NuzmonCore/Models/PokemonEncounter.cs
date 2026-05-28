namespace NuzmonCore.Models
{
    public class PokemonEncounter
    {
        public int ID { get; set; }

        public string name { get; set; } = "";

        public int level { get; set; } = 1;

        public bool isShiny { get; set; }

        public string location { get; set; } = "";

    }
}
