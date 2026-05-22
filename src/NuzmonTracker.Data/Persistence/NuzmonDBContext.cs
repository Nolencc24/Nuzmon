using Microsoft.EntityFrameworkCore;
using NuzmonCore.Models;

namespace NuzmonTracker.Data.Persistence
{
    public class NuzmonDBContext : DbContext
    {
        public DbSet<PokemonEncounter> Encounters => Set<PokemonEncounter>();
        public NuzmonDBContext(DbContextOptions<NuzmonDBContext> options) : base(options)
        {
        }
    }
}
