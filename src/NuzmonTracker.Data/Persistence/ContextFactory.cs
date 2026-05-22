using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;
using NuzmonTracker.Data.Persistence;

namespace Nuzmon.Data.Persistence;

public class NuzmonDbContextFactory : IDesignTimeDbContextFactory<NuzmonDBContext>
{
    public NuzmonDBContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<NuzmonDBContext>();

        optionsBuilder.UseSqlite("Data Source=nuzmon.db");

        return new NuzmonDBContext(optionsBuilder.Options);
    }
}