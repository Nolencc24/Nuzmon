using Microsoft.EntityFrameworkCore;
using NuzmonCore.Models;

namespace NuzmonTracker.Data.Persistence
{
    public class NuzmonDBContext : DbContext
    {
        public DbSet<PokemonEncounter> Encounters => Set<PokemonEncounter>();
        public DbSet<Pokemon> BaseStats => Set<Pokemon>();
        public NuzmonDBContext(DbContextOptions<NuzmonDBContext> options) : base(options)
        {
        }
    }
}
